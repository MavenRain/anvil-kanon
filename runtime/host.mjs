import { readFile } from 'node:fs/promises';
import { setFlagsFromString } from 'node:v8';

// Node 23 can deadlock at shutdown while Maglev waits for a main-thread GC.
// Set this before warming the byte adapter; other Node versions keep defaults.
if (process.versions.node.startsWith('23.')) setFlagsFromString('--no-maglev');

// Yojson.Safe chooses 16 significant digits when they round-trip, otherwise 17.
export function floatText(n) {
  if (Number.isNaN(n)) return 'NaN';
  if (!Number.isFinite(n)) return n < 0 ? '-Infinity' : 'Infinity';
  if (Object.is(n, -0)) return '-0.0';
  function g(digits) {
    const [mantissa, exponent] = n.toExponential(digits - 1).split('e');
    const exp = Number(exponent);
    if (exp < -4 || exp >= digits) return `${mantissa.replace(/\.?0+$/, '')}e${exp < 0 ? '-' : '+'}${String(Math.abs(exp)).padStart(2, '0')}`;
    return n.toFixed(Math.max(0, digits - exp - 1)).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  }
  const first = g(16);
  const result = Number(first) === n ? first : g(17);
  return /[.e]/.test(result) ? result : `${result}.0`;
}

export async function load(wasm = new URL('../build/anvil.wasm', import.meta.url)) {
  const { instance } = await WebAssembly.instantiate(await readFile(wasm), {});
  const w = instance.exports;
  function bytes(input) {
    const buffer = Buffer.isBuffer(input) ? input : Buffer.from(input);
    let value = w.emptyBytes();
    for (let i = buffer.length - 1; i >= 0; --i) value = w.consBytes(buffer[i], value);
    return value;
  }
  function buffer(value) {
    const out = [];
    while (!w.bytesEmpty(value)) { out.push(w.bytesHead(value)); value = w.bytesTail(value); }
    return Buffer.from(out);
  }
  const text = value => buffer(value).toString('utf8');
  function integer(n) {
    if (typeof n !== 'bigint' && !Number.isSafeInteger(n)) throw new RangeError('An exact integer is required');
    const result = w.parseInteger(bytes(String(n)));
    if (!w.intResultOk(result)) throw new RangeError('Outside the OCaml integer range');
    return w.intResultValue(result);
  }
  function json(value) {
    if (value === null) return w.jsonNullValue();
    if (typeof value === 'boolean') return w.jsonBoolValue(value ? w.boolTrue() : w.boolFalse());
    if (typeof value === 'string') return w.jsonStringValue(bytes(value));
    if (typeof value === 'bigint') return w.jsonIntValue(integer(value));
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) throw new TypeError('Non-finite input requires the explicit text interface');
      if (Number.isInteger(value) && !Number.isSafeInteger(value)) throw new RangeError('Use BigInt or JSON text for large integers');
      return Number.isSafeInteger(value) && !Object.is(value, -0) ? w.jsonIntValue(integer(value)) : w.jsonFloatValue(bytes(floatText(value)));
    }
    if (Array.isArray(value)) {
      let xs = w.jsonArrayEmpty();
      for (let i = value.length - 1; i >= 0; --i) xs = w.jsonArrayPush(json(value[i]), xs);
      return w.jsonArrayValue(xs);
    }
    if (typeof value === 'object') {
      let xs = w.jsonObjectEmpty();
      for (const [key, item] of Object.entries(value).reverse()) xs = w.jsonObjectPush(bytes(key), json(item), xs);
      return w.jsonObjectValue(xs);
    }
    throw new TypeError('Unsupported JSON input');
  }
  // Build Wasm values directly, retaining member order, duplicates and numeric tags.
  function parse(source) {
    let i = 0;
    const fail = detail => { throw new SyntaxError(`${detail} at offset ${i}`); };
    const space = () => { while (/[\t\r\n ]/.test(source[i] ?? '') && i < source.length) ++i; };
    function string() {
      const start = i++;
      while (i < source.length) {
        const c = source[i++];
        if (c === '\\') { ++i; continue; }
        if (c === '"') {
          const s = JSON.parse(source.slice(start, i));
          for (let k = 0; k < s.length; ++k) {
            const n = s.charCodeAt(k);
            if (n >= 0xd800 && n <= 0xdbff) { const low = s.charCodeAt(++k); if (!(low >= 0xdc00 && low <= 0xdfff)) fail('Unpaired surrogate'); }
            else if (n >= 0xdc00 && n <= 0xdfff) fail('Unpaired surrogate');
          }
          return s;
        }
      }
      return fail('Unterminated string');
    }
    function value() {
      space();
      if (source[i] === '"') return w.jsonStringValue(bytes(string()));
      if (source[i] === '{') {
        ++i; space(); const entries = [];
        if (source[i] !== '}') for (;;) {
          space(); if (source[i] !== '"') fail('Expected object key'); const key = string();
          space(); if (source[i++] !== ':') fail('Expected colon'); entries.push([key, value()]);
          space(); if (source[i] !== ',') break; ++i;
        }
        if (source[i++] !== '}') fail('Expected closing brace');
        let xs = w.jsonObjectEmpty();
        for (const [key, v] of entries.reverse()) xs = w.jsonObjectPush(bytes(key), v, xs);
        return w.jsonObjectValue(xs);
      }
      if (source[i] === '[') {
        ++i; space(); const entries = [];
        if (source[i] !== ']') for (;;) { entries.push(value()); space(); if (source[i] !== ',') break; ++i; }
        if (source[i++] !== ']') fail('Expected closing bracket');
        let xs = w.jsonArrayEmpty(); for (const v of entries.reverse()) xs = w.jsonArrayPush(v, xs);
        return w.jsonArrayValue(xs);
      }
      for (const token of ['null', 'true', 'false']) if (source.startsWith(token, i)) {
        i += token.length;
        if (token === 'null') return w.jsonNullValue();
        if (token === 'true' || token === 'false') return w.jsonBoolValue(token === 'true' ? w.boolTrue() : w.boolFalse());
      }
      const token = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(source.slice(i))?.[0];
      if (!token) return fail('Expected JSON value');
      i += token.length;
      if (/[.eE]/.test(token)) {
        const n = Number(token); if (!Number.isFinite(n)) fail('Non-finite JSON number');
        return w.jsonFloatValue(bytes(floatText(n)));
      }
      const n = BigInt(token);
      return n >= -(1n << 62n) && n < (1n << 62n) ? w.jsonIntValue(integer(n)) : w.jsonIntLiteralValue(bytes(token));
    }
    try {
      const result = value(); space(); if (i !== source.length) fail('Trailing input');
      return { ok: true, value: result };
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
      return { ok: false, error: { kind: 'Value', detail: error.message } };
    }
  }
  return { w, bytes, buffer, text, integer, json, parse };
}
