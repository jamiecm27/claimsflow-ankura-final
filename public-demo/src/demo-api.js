import { strFromU8, unzipSync } from 'fflate';
import sampleClaims from './claims.json';

const MB = 1024 * 1024;
const sessionKey = 'claimsflow-guest';
const session = sessionStorage.getItem(sessionKey) || crypto.randomUUID();
sessionStorage.setItem(sessionKey, session);

const evidenceUrls = new Map();
const samples = {
  'CLM-001': ['SMA-778821-GA', '17 May 2026, 08:45', 'Rear-end collision with rear bumper and boot damage. No injuries reported.', 'Fast-track', '4250'],
  'CLM-002': ['GLC-IL-4400192', '16 May 2026, 21:20', 'Hit-and-run collision. An occupant reported neck pain.', 'Specialist Queue'],
  'CLM-003': ['DSI-AZ-330782', '14 May 2026, 06:10', 'Vehicle recovered after theft with damage to the window and ignition.', 'Standard Queue'],
  'CLM-004': ['PNI-WA-905512', '15 May 2026, 17:35', 'Collision involving two vehicles and a guardrail.', 'Specialist Queue'],
  'CLM-005': ['LSA-TX-702244', '18 May 2026, 01:15', 'Vandalism with damage to passenger-side glass.', 'Fast-track', '1150'],
  'CLM-006': ['RMC-CO-661209', '13 May 2026, 16:40', 'Hail damage to hood, roof, and boot. Inspection pending.', 'Standard Queue'],
};
const database = new Promise((resolve, reject) => {
  const request = indexedDB.open('claimsflow-public-demo', 1);
  request.onupgradeneeded = () => request.result.createObjectStore('sessions');
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error);
});

async function stored(mode, action) {
  const db = await database;
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('sessions', mode);
    const request = action(transaction.objectStore('sessions'));
    transaction.oncomplete = () => resolve(request.result);
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });
}

async function getState() {
  return (await stored('readonly', store => store.get(session))) || {
    cases: structuredClone(sampleClaims), attempts: [], evaluations: [], documents: {},
  };
}

let writeQueue = Promise.resolve();
function update(change) {
  const operation = writeQueue.then(async () => {
    const state = await getState();
    const result = await change(state);
    await stored('readwrite', store => store.put(state, session));
    return structuredClone(result);
  });
  writeQueue = operation.catch(() => {});
  return operation;
}

function fail(detail) {
  throw Object.assign(new Error(detail), { response: { data: { detail } } });
}

function getCase(state, id) {
  const claim = state.cases.find(item => item.id === id);
  if (!claim) fail('This claim is unavailable.');
  return claim;
}

function prepareEvidence(state) {
  for (const [id, file] of Object.entries(state.documents)) {
    if (!evidenceUrls.has(id)) evidenceUrls.set(id, URL.createObjectURL(file));
  }
}

export function documentUrl(caseId, filename) {
  return evidenceUrls.get(filename) || `/evidence/${encodeURIComponent(caseId)}/${encodeURIComponent(filename)}`;
}

async function analyse(claim, live = false) {
  if (live && Object.hasOwn(samples, claim.id)) {
    const response = await fetch('/api/gemini/analyse', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caseId: claim.id }),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok || result?.provider !== 'gemini') {
      fail(result?.detail || 'The site returned an unexpected response. Try the claim again.');
    }
    return result;
  }

  const sample = samples[claim.id];
  const fields = sample ? {
    policyNumber: sample[0], incidentDate: sample[1], description: sample[2],
    claimType: 'Motor', assetType: 'Vehicle', ...(sample[4] ? { estimatedDamage: sample[4] } : {}),
  } : {};
  return {
    id: crypto.randomUUID(), extractedFields: fields, provider: sample ? 'demo_sample' : 'demo_manual',
    recommendedRoute: sample?.[3] || 'Manual Review', apiSeconds: sample ? 1.2 : 0,
    reasoning: sample ? 'Sample suggestion based on the supplied synthetic evidence.' : 'Use the uploaded evidence to choose a route.',
    warning: sample ? '' : 'AI extraction is available for the six supplied synthetic claims. Review uploaded claims manually.',
  };
}

async function addDocuments(state, claim, files) {
  if (!files.length || claim.documents.length + files.length > 8) fail('Use 1–8 PDFs per claim in total.');
  for (const file of files) {
    const header = new Uint8Array(await file.slice(0, 5).arrayBuffer());
    if (file.size > 8 * MB || new TextDecoder().decode(header) !== '%PDF-') fail('Each attachment must be a PDF of up to 8 MB.');
  }
  claim.documentLabels ??= {};
  for (const file of files) {
    const id = crypto.randomUUID() + '.pdf';
    state.documents[id] = new Blob([file], { type: 'application/pdf' });
    claim.documents.push(id);
    claim.documentLabels[id] = file.name;
  }
}

async function createClaim(state, title, files) {
  if (!title.trim()) fail('Enter a title for the synthetic claim.');
  const claim = { id: 'DEMO-' + String(state.cases.length + 1).padStart(3, '0'), title: title.trim(), documents: [], status: 'New' };
  await addDocuments(state, claim, files);
  state.cases.push(claim);
  return claim;
}

async function bulkImport(state, file) {
  if (!file || file.size > 100 * MB) fail('Choose a ZIP of up to 100 MB.');
  let expanded = 0;
  let contents;
  try {
    contents = unzipSync(new Uint8Array(await file.arrayBuffer()), {
      filter: item => {
        const name = item.name;
        if (name !== 'manifest.csv' && !/^[^/]+\/[^/]+\.pdf$/i.test(name)) return false;
        expanded += item.originalSize;
        if (expanded > 100 * MB || item.originalSize > (name === 'manifest.csv' ? MB : 8 * MB)) {
          fail('The ZIP expands beyond the demo limits.');
        }
        return true;
      },
    });
  } catch (error) {
    fail(error.response?.data.detail || 'The ZIP could not be read.');
  }
  const groups = new Map();
  for (const [path, bytes] of Object.entries(contents)) {
    if (path === 'manifest.csv') continue;
    const [folder, name] = path.split('/');
    if (!groups.has(folder)) groups.set(folder, []);
    groups.get(folder).push(new File([bytes], name, { type: 'application/pdf' }));
  }
  if (!groups.size || groups.size > 100) fail('Include 1–100 claim folders containing PDFs.');
  const titles = new Map();
  if (contents['manifest.csv']) {
    for (const line of strFromU8(contents['manifest.csv']).split(/\r?\n/).slice(1)) {
      const match = line.match(/^([^,]+),\s*(?:"((?:[^"]|"")*)"|(.*))$/);
      if (match) titles.set(match[1].trim(), match[2]?.replaceAll('""', '"') ?? match[3]);
    }
  }
  for (const [folder, files] of groups) await createClaim(state, titles.get(folder) || folder, files);
  return { imported: groups.size };
}

async function evaluate(state, settings, onProgress) {
  const cases = [];
  for (const id of settings.caseIds) {
    try {
      const result = await analyse(getCase(state, id), settings.live);
      cases.push({
        caseId: id, status: result.provider === 'demo_manual' ? 'manual' : 'ok',
        apiSeconds: result.provider === 'demo_manual' ? null : result.apiSeconds,
        recommendedRoute: result.recommendedRoute,
      });
    } catch (error) {
      cases.push({ caseId: id, status: 'error', warning: error.message });
    }
    onProgress?.(cases.length);
  }
  const count = cases.filter(item => item.status === 'ok').length;
  const simulatedMinutes = settings.simulateHuman ? cases.reduce((sum, item) => (
    sum + Number(settings.manualMinutes) + getCase(state, item.caseId).documents.length * Number(settings.documentMinutes)
      + Number(settings.complexityMinutes)
  ), 0) / Math.max(cases.length, 1) : null;
  const run = {
    id: crypto.randomUUID(), createdAt: new Date().toISOString(), settings, cases,
    summary: {
      totalCases: cases.length, geminiSuccesses: count, fallbacks: cases.filter(item => item.status === 'manual').length, errors: cases.filter(item => item.status === 'error').length,
      simulatedHumanMinutes: simulatedMinutes,
      simulatedHumanCost: simulatedMinutes === null ? null : simulatedMinutes * settings.hourlyRate / 60,
      simulatedHumanFieldAccuracy: settings.simulateHuman ? (1 - settings.humanErrorRate) * 100 : null,
      simulatedHumanRoutingAgreement: settings.simulateHuman ? (1 - settings.humanRoutingErrorRate) * 100 : null,
    },
  };
  state.evaluations.unshift(run);
  return run;
}

export async function downloadReviewReport(claim, review) {
  const { jsPDF } = await import('jspdf');
  const report = new jsPDF({ unit: 'mm' });
  report.setFontSize(18);
  report.text('ClaimsFlow | Synthetic claim review', 16, 20);
  report.setFontSize(11);
  const fields = Object.entries(review.fields).filter(([, value]) => value);
  const lines = [
    `Claim: ${claim.id} - ${claim.title}`,
    `Review: ${review.mode === 'ai' ? 'AI-assisted demo' : 'Human-only'}`,
    `Final route: ${review.finalRoute}`,
    `Rationale: ${review.decisionReason || '—'}`,
    ...fields.map(([key, value]) => `${key.replace(/([A-Z])/g, ' $1')}: ${value}`),
  ];
  let y = 30;
  for (const entry of lines) {
    for (const line of report.splitTextToSize(entry, 175)) {
      if (y > 280) { report.addPage(); y = 20; }
      report.text(line, 16, y);
      y += 5;
    }
  }
  report.save(`ClaimsFlow_${claim.id}_review.pdf`);
}

const reply = data => ({ data });

export default {
  async get(path) {
    if (path === '/api/gemini/status') {
      try {
        const response = await fetch(path, { cache: 'no-store' });
        if (response.ok) return reply(await response.json());
      } catch {
        // Local builds can demonstrate the sample workflow without a Worker.
      }
      return reply({ available: false, mode: 'sample' });
    }
    const state = await getState();
    if (path === '/workbench/cases') {
      prepareEvidence(state);
      return reply(state.cases);
    }
    if (path === '/workbench/attempts') return reply(state.attempts);
    if (path === '/workbench/evaluation/runs') return reply(state.evaluations);
    const history = path.match(/^\/workbench\/cases\/([^/]+)\/history$/);
    if (history) return reply({ case: getCase(state, history[1]), attempts: state.attempts.filter(attempt => attempt.caseId === history[1]) });
    fail('This action is unavailable in the public demo.');
  },

  async post(path, value, onProgress) {
    if (path === '/api/logout') {
      await writeQueue;
      await stored('readwrite', store => store.delete(session));
      sessionStorage.removeItem(sessionKey);
      return reply({});
    }
    const review = path.match(/^\/workbench\/cases\/([^/]+)\/ai-process$/);
    if (review) return reply(await analyse(getCase(await getState(), review[1]), value?.live));
    const result = await update(async state => {
      if (path === '/workbench/cases') return createClaim(state, value.get('title'), value.getAll('documents'));
      if (path === '/workbench/cases/bulk-import') return bulkImport(state, value.get('archive'));
      if (path === '/workbench/evaluation/run') return evaluate(state, value, onProgress);
      if (path === '/workbench/attempts') {
        getCase(state, value.caseId).status = 'Reviewed';
        const record = { ...value, id: crypto.randomUUID(), submittedAt: new Date().toISOString(), isRevision: false };
        state.attempts.push(record);
        return record;
      }
      const docs = path.match(/^\/workbench\/cases\/([^/]+)\/documents$/);
      if (docs) {
        const claim = getCase(state, docs[1]);
        await addDocuments(state, claim, value.getAll('documents'));
        prepareEvidence(state);
        return claim;
      }
      const revision = path.match(/^\/workbench\/cases\/([^/]+)\/revisions$/);
      if (revision) {
        const original = state.attempts.find(item => item.id === value.basedOnAttemptId && item.caseId === revision[1]);
        if (!original) fail('This saved review is unavailable.');
        const record = { ...original, ...value, id: crypto.randomUUID(), submittedAt: new Date().toISOString(), isRevision: true };
        state.attempts.push(record);
        return record;
      }
      fail('This action is unavailable to a demo analyst.');
    });
    return reply(result);
  },
};
