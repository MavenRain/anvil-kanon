import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const cases = {
  metadata: ['objectMetaT', [{}, { name: '', uid: -1, labels: {} }, { ownerReferences: [] },
    { labels: { z: '1', a: '2' }, finalizers: ['a', 'a'] }, { uid: null }, { uid: '1' }, { labels: { a: 1 } }]],
  owner: ['ownerReferenceT', [{ kind: 'Pod', name: 'p', uid: 1 },
    { kind: { customResource: 'vreplicaset' }, name: '', uid: -1, controller: true },
    {}, { kind: 'Pod', uid: 1 }, { kind: 'Pod', name: 'p', uid: 1, controller: 1 }]],
  kind: ['commonKind', ['Pod', 'ConfigMap', 'Unknown', { customResource: 'x' },
    { customResource: 'x', extra: true }, { customResource: 1 }]],
  podSpec: ['podSpecT', [{ containers: [] }, { containers: [{ name: 'main', image: 'v1', command: ['a', 'b'] }] },
    { containers: [], affinity: {} }, { containers: [], affinity: null }, { containers: [], affinity: true },
    { containers: [], imagePullSecrets: [{ ignored: 'x' }] }, { containers: [], hostNetwork: 1 }, {}, { containers: {} }]],
  template: ['podTemplateSpecT', [{}, { metadata: { labels: { app: 'x' } }, spec: { containers: [] } }, { spec: {} }]],
  container: ['containerT', [{ name: 'main' }, { name: 'main', readinessProbe: { tcpSocket: { port: 90 } } },
    { name: 'main', securityContext: {} }, { name: 'main', securityContext: false },
    { name: 'main', volumeMounts: [{ name: 'v', mountPath: '/x', readOnly: true }] }, {}]],
  volume: ['volumeT', [{ name: 'v' }, { name: 'v', downwardAPI: { items: [] } },
    { name: 'v', persistentVolumeClaim: { claimName: 'p', readOnly: true } },
    { name: 'v', projected: { sources: [{ secret: { name: 's', items: [{ key: 'a', path: 'b' }] } }] } }, {}]],
  pvc: ['persistentVolumeClaimT', [{ metadata: {} }, { metadata: {}, status: {} }, { metadata: {}, status: false },
    { metadata: { name: 'p' }, spec: { accessModes: ['ReadWriteOnce'], resources: { requests: { storage: '1Gi' } } } }]],
  selector: ['labelSelectorT', [{}, { matchLabels: {} }, { matchLabels: { a: 'b' } }, { matchLabels: { a: false } }]],
  statefulSpec: ['statefulSetSsSpec', [{ selector: {}, serviceName: '', template: {} },
    { selector: {}, serviceName: 's', template: {}, replicas: -1, volumeClaimTemplates: [{ metadata: { name: 'data' } }] },
    { selector: {} }]],
  strategy: ['deploymentStrategyT', [{}, { type: 'RollingUpdate', rollingUpdate: { maxSurge: 2 } }, { type: 'Other' }]],
};

test('field codecs agree with OCaml on nested values and malformed inputs', async () => {
  const { w, json, text } = await load();
  const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
  for (const [name, [prefix, inputs]] of Object.entries(cases)) {
    for (const input of [...inputs, null, [], true, 19, 'text']) {
      const result = spawnSync(oracle, ['codec', name, JSON.stringify(input)], { encoding: 'utf8' });
      assert.equal(result.status, 0, result.error?.message ?? result.stderr);
      const expected = result.stdout.trim();
      const context = `${name}: ${JSON.stringify(input)}`;
      let actual;
      try {
        actual = text(w[`${prefix}DecodeRender`](json(input)));
      } catch (error) {
        assert.fail(`${context}: ${error.message}`);
      }
      if (expected.startsWith('error: ') || actual.startsWith('error: ')) assert.equal(actual, expected, context);
      else assert.deepEqual(JSON.parse(actual), JSON.parse(expected), context);
    }
  }
});
