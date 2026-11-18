import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Activity, ArrowLeft, BarChart3, BrainCircuit, CheckCircle2, Clock3, FileText, Inbox, RotateCcw, ShieldCheck, Sparkles, Users, UploadCloud, Settings, History, PoundSterling, Target } from 'lucide-react';
import './App.css';
import { APP_VERSION } from './version';

const API = import.meta.env.VITE_API_BASE_URL || '';
const ROUTES = ['Fast-track', 'Standard Queue', 'Manual Review', 'Specialist Queue', 'Investigation Flag'];
const GROUPS = [
  ['Policy details', ['policyNumber','policyholderName','effectiveDates']],
  ['Incident', ['incidentDate','incidentTime','location','description']],
  ['People', ['claimant','thirdParties','contactDetails']],
  ['Asset and loss', ['assetType','assetId','estimatedDamage','claimType','attachments','initialEstimate']],
];
const FIELDS = GROUPS.flatMap(group => group[1]);
const LABEL = Object.fromEntries(FIELDS.map(x => [x, x.replace(/([A-Z])/g,' $1').replace(/^./, s => s.toUpperCase())]));
const seconds = n => `${Math.floor(n/60)}m ${String(Math.floor(n%60)).padStart(2,'0')}s`;

export default function App() {
  const [me,setMe] = useState(null);
  useEffect(()=>{axios.get(`${API}/api/me`).then(r=>setMe(r.data)).catch(()=>{location.href='/login';});},[]);
  const [tab, setTab] = useState('inbox');
  const [geminiKey,setGeminiKey] = useState('');
  const [geminiStatus,setGeminiStatus] = useState(null);
  const [geminiSaving,setGeminiSaving] = useState(false);
  const [geminiTesting,setGeminiTesting] = useState(false);
  const [geminiTestResult,setGeminiTestResult] = useState(null);
  const [geminiMessage,setGeminiMessage] = useState('');
  useEffect(()=>{axios.get(`${API}/api/gemini-settings`).then(r=>setGeminiStatus(r.data)).catch(()=>setGeminiMessage('Cannot check Gemini settings.'));},[]);
  const saveGeminiKey=async()=>{
    setGeminiSaving(true);setGeminiMessage('');
    try{
      const r=await axios.post(`${API}/api/gemini-settings`,{api_key:geminiKey});
      setGeminiStatus(r.data);setGeminiKey('');setGeminiTestResult(null);setGeminiMessage('Key saved in macOS Keychain. Click Test Gemini Connection to verify access.');
    }catch(e){setGeminiMessage(e.response?.data?.detail||'Could not save the key.');}
    finally{setGeminiSaving(false);}
  };

  const testGemini=async()=>{
    setGeminiTesting(true);setGeminiTestResult(null);
    try { const r=await axios.post(`${API}/api/gemini-test`);setGeminiTestResult(r.data); }
    catch(e){setGeminiTestResult({ok:false,message:e.response?.data?.detail||e.message||'Connection test failed.'});}
    finally {setGeminiTesting(false);}
  };

  const [cases, setCases] = useState([]);
  const [claimsLoaded, setClaimsLoaded] = useState(false);
  const [attempts, setAttempts] = useState([]);
  const [selected, setSelected] = useState(null);
  const [mode, setMode] = useState(null);
  const [fields, setFields] = useState({});
  const [route, setRoute] = useState('Manual Review');
  const [reason, setReason] = useState('');
  const [ai, setAi] = useState(null);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [search,setSearch]=useState('');
  const [bulkFile,setBulkFile]=useState(null);
  const [bulkBusy,setBulkBusy]=useState(false);
  const [newTitle,setNewTitle]=useState('');
  const [newDocs,setNewDocs]=useState([]);
  const [extraDocs,setExtraDocs]=useState([]);
  const [uploading,setUploading]=useState(false);
  const [history,setHistory]=useState(null);
  const [savedRecord,setSavedRecord]=useState(null);
  const [editingRecord,setEditingRecord]=useState(false);
  const [evaluation,setEvaluation]=useState(null);
  const [evaluationBusy,setEvaluationBusy]=useState(false);
  const [evalSelected,setEvalSelected]=useState(null);
  const [evalSearch,setEvalSearch]=useState('');
  const [simulateHuman,setSimulateHuman]=useState(true);
  const [humanErrorRate,setHumanErrorRate]=useState(5);
  const [humanRoutingErrorRate,setHumanRoutingErrorRate]=useState(5);
  const [documentMinutes,setDocumentMinutes]=useState(1.5);
  const [complexityMinutes,setComplexityMinutes]=useState(2);
  const [evaluationError,setEvaluationError]=useState('');
  const [manualMinutes,setManualMinutes]=useState(10);
  const [verificationMinutes,setVerificationMinutes]=useState(3);
  const [hourlyRate,setHourlyRate]=useState(25);
  const [apiCost,setApiCost]=useState(0.02);
  const [monthlyClaims,setMonthlyClaims]=useState(1000);
  const started = useRef(null);
  const elapsedBase = useRef(0);
  const timer = useRef(null);
  const fetchData = async () => {
    const [c,a] = await Promise.all([axios.get(`${API}/workbench/cases`), axios.get(`${API}/workbench/attempts`)]);
    setCases(c.data); setAttempts(a.data); setClaimsLoaded(true);
  };
  useEffect(() => { axios.get(`${API}/workbench/evaluation/runs`).then(r=>setEvaluation(r.data[0]||null)).catch(()=>{}); }, []);
  const runEvaluation=async()=>{ setEvaluationBusy(true);setEvaluationError('');try {const r=await axios.post(`${API}/workbench/evaluation/run`,{manualMinutes:Number(manualMinutes),verificationMinutes:Number(verificationMinutes),hourlyRate:Number(hourlyRate),apiCost:Number(apiCost),caseIds:evalSelected===null?cases.map(c=>c.id):evalSelected,simulateHuman,humanErrorRate:Number(humanErrorRate)/100,humanRoutingErrorRate:Number(humanRoutingErrorRate)/100,documentMinutes:Number(documentMinutes),complexityMinutes:Number(complexityMinutes)});setEvaluation(r.data);}catch(e){setEvaluationError(e.response?.data?.detail||'Evaluation failed. Check the server and Gemini API settings.');}finally{setEvaluationBusy(false);} };
  useEffect(() => { fetchData().catch(() => setError('Cannot reach ClaimsFlow server. Check that the Mac mini is running.')); }, []);
  useEffect(() => () => clearInterval(timer.current), []);
  const begin = (c,m) => {
    clearInterval(timer.current);
    setSavedRecord(null); setEditingRecord(false);
    setSelected(c); setMode(m); setFields({}); setRoute('Manual Review'); setReason(''); setAi(null);
    setError(''); setNotice(''); setElapsed(0); elapsedBase.current = 0;
    started.current = performance.now(); setRunning(true);
    timer.current = setInterval(() => setElapsed(elapsedBase.current + (performance.now()-started.current)/1000), 200);
    setTab('review');
  };
  const openRecord = async (c, attemptId=null) => {
    try {
      const {data} = await axios.get(`${API}/workbench/cases/${c.id}/history`);
      const record = attemptId ? data.attempts.find(a=>a.id===attemptId) : data.attempts[data.attempts.length-1];
      if (!record) return setError('No submitted review exists for this claim yet.');
      clearInterval(timer.current); setRunning(false); setElapsed(0);
      setSelected(data.case); setSavedRecord(record); setEditingRecord(false);
      setMode(record.mode); setFields({...record.fields}); setRoute(record.finalRoute);
      setReason(record.decisionReason || ''); setAi(null); setError(''); setNotice(''); setTab('review');
    } catch(e) { setError('Could not load the saved claim record.'); }
  };
  const saveRevision = async () => {
    if (!savedRecord) return;
    if (!reason.trim()) return setError('Enter a reason for the correction before saving a new version.');
    setBusy(true); setError('');
    try {
      await axios.post(`${API}/workbench/cases/${selected.id}/revisions`, {
        basedOnAttemptId:savedRecord.id, fields, finalRoute:route, decisionReason:reason
      });
      await fetchData(); await openRecord(selected);
      setNotice('New version saved. The previous submitted record remains in history.');
    } catch(e) { setError(e.response?.data?.detail || 'Could not save correction.'); }
    finally { setBusy(false); }
  };
  const toggleTimer = () => {
    if (running) { elapsedBase.current += (performance.now()-started.current)/1000; clearInterval(timer.current); setElapsed(elapsedBase.current); setRunning(false); }
    else { started.current = performance.now(); setRunning(true); timer.current = setInterval(() => setElapsed(elapsedBase.current+(performance.now()-started.current)/1000),200); }
  };
  const processAI = async () => {
    setBusy(true); setError('');
    try {
      const {data} = await axios.post(`${API}/workbench/cases/${selected.id}/ai-process`);
      const previousSuggestions = ai?.extractedFields ?? {};
      setFields(current => {
        const next = { ...current };
        for (const key of FIELDS) {
          if ((current[key] ?? '') === (previousSuggestions[key] ?? '')) {
            next[key] = data.extractedFields?.[key] ?? '';
          }
        }
        return next;
      });
      setAi(data);
      setRoute(data.recommendedRoute);
      setReason('');
    } catch(e) { setError(e.response?.data?.detail || 'AI processing failed. Check the backend and Gemini configuration.'); }
    finally { setBusy(false); }
  };
  const submit = async () => {
    if (mode==='ai' && !ai) return setError('Run the AI analysis before submitting.');
    if (mode==='ai' && ai.recommendedRoute!==route && !reason.trim()) return setError('Explain why you overrode the AI recommendation.');
    setBusy(true); setError('');
    const total = running ? elapsedBase.current + (performance.now()-started.current)/1000 : elapsedBase.current;
    try {
      await axios.post(`${API}/workbench/attempts`, {
        caseId: selected.id,
        mode,
        elapsedSeconds: total,
        fields,
        finalRoute: route,
        decisionReason: reason,
        aiAttemptId: ai?.id,
        aiExtractedFields: ai?.extractedFields,
      });
      clearInterval(timer.current); setRunning(false); setSelected(null); setMode(null); setNotice('Review saved. Open History to see it, or start another review.');
      await fetchData(); setTab('inbox');
    } catch(e) { setError(e.response?.data?.detail || 'Could not save the review.'); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    if (!window.confirm('Reset all synthetic workbench cases and timing attempts?')) return;
    try {await axios.post(`${API}/workbench/reset`); await fetchData(); setTab('inbox'); setNotice('Demo data reset.');}
    catch(e){setError(e.response?.data?.detail||'Reset failed.');}
  };
  const uploadCase=async()=>{
    if(!newTitle.trim()||!newDocs.length)return setError('Enter a fictional claim title and choose PDF evidence.');
    setUploading(true);setError('');
    try {const fd=new FormData();fd.append('title',newTitle);Array.from(newDocs).forEach(d=>fd.append('documents',d));await axios.post(`${API}/workbench/cases`,fd);setNewTitle('');setNewDocs([]);await fetchData();setNotice('Synthetic claim and documents added to inbox.');}
    catch(e){setError(e.response?.data?.detail||'Could not upload claim. Use text-based PDFs under 8 MB each.');}
    finally{setUploading(false);}
  };
  const importBulk=async()=>{
    if(!bulkFile)return setError('Choose a ZIP of fictional claim folders.');
    setBulkBusy(true);setError('');
    try {const fd=new FormData();fd.append('archive',bulkFile);const {data}=await axios.post(`${API}/workbench/cases/bulk-import`,fd);await fetchData();setNotice(`${data.imported} synthetic claims imported successfully.`);setBulkFile(null);}
    catch(e){setError(e.response?.data?.detail||'Bulk import failed. Check ZIP structure and PDF limits.');}
    finally{setBulkBusy(false);}
  };
  const addEvidence=async()=>{
    if(!extraDocs.length)return;
    setUploading(true);setError('');
    try {const fd=new FormData();Array.from(extraDocs).forEach(d=>fd.append('documents',d));const {data}=await axios.post(`${API}/workbench/cases/${selected.id}/documents`,fd);setSelected(data);setExtraDocs([]);await fetchData();setNotice('Supporting evidence added to this claim.');}
    catch(e){setError(e.response?.data?.detail||'Could not add evidence.');}
    finally{setUploading(false);}
  };
  const showHistory=async(c)=>{try{const {data}=await axios.get(`${API}/workbench/cases/${c.id}/history`);setHistory(data);setTab('history');setError('');}catch(e){setError('Could not load saved claim history.');}};
  const avg = m => {const xs=attempts.filter(a=>a.mode===m && !a.isRevision); return xs.length ? xs.reduce((s,a)=>s+a.elapsedSeconds,0)/xs.length : null;};
  const manualAvg=avg('manual'), aiAvg=avg('ai');
  const scored=attempts.filter(a=>a.quality?.referenceAvailable && !a.isRevision);
  const qualityAvg=m=>{const xs=scored.filter(a=>a.mode===m&&a.quality.fieldAccuracy!==null);return xs.length?xs.reduce((v,a)=>v+a.quality.fieldAccuracy,0)/xs.length:null;};
  const routeAvg=m=>{const xs=scored.filter(a=>a.mode===m&&!a.isRevision);return xs.length?100*xs.filter(a=>a.quality.routeAgreement).length/xs.length:null;};
  const money=n=>Number.isFinite(n)?`£${n.toFixed(2)}`:'—';
  const manualCost=manualAvg===null?null:manualAvg/3600*Number(hourlyRate);
  const assistedCost=aiAvg===null?null:aiAvg/3600*Number(hourlyRate)+Number(apiCost);
  const evaluatedIds = evaluation?.cases?.map(c=>c.caseId) || [];
  const completedAI = evaluation?.cases?.filter(c=>c.status==='ok') || [];
  const runSettings = evaluation?.settings || {};
  const runRate = Number(runSettings.hourlyRate ?? hourlyRate);
  const runVerification = Number(runSettings.verificationMinutes ?? verificationMinutes);
  const runApiCost = Number(runSettings.apiCost ?? apiCost);
  const aiTotalMinutes = completedAI.length ? completedAI.reduce((n,c)=>n+(Number(c.apiSeconds)||0)/60+runVerification,0)/completedAI.length : null;
  const aiCostPerClaim = aiTotalMinutes===null?null:runVerification*runRate/60+runApiCost;
  const simMinutes = evaluation?.summary?.simulatedHumanMinutes ?? null;
  const simCost = evaluation?.summary?.simulatedHumanCost ?? null;
  const latestManual = evaluatedIds.map(id=>[...attempts].reverse().find(a=>a.caseId===id&&a.mode==='manual'&&!a.isRevision)).filter(Boolean);
  const pairedManual = completedAI.map(c=>[...attempts].reverse().find(a=>a.caseId===c.caseId&&a.mode==='manual'&&!a.isRevision)).filter(Boolean);
  const pairedAI = completedAI.filter(c=>pairedManual.some(a=>a.caseId===c.caseId));
  const mean = (xs, fn) => xs.length ? xs.reduce((n,x)=>n+fn(x),0)/xs.length : null;
  const manualMinutesMeasured = mean(latestManual,a=>a.elapsedSeconds/60);
  const manualCostMeasured = manualMinutesMeasured===null?null:manualMinutesMeasured*runRate/60;
  const pairedManualMinutes = mean(pairedManual,a=>a.elapsedSeconds/60);
  const pairedAIMinutes = mean(pairedAI,c=>(Number(c.apiSeconds)||0)/60+runVerification);
  const pairedManualCost = pairedManualMinutes===null?null:pairedManualMinutes*runRate/60;
  const pairedAICost = pairedAIMinutes===null?null:runVerification*runRate/60+runApiCost;
  const fmtMin = n=>n==null?'—':`${n.toFixed(1)} min`;
  const fmtPct = n=>n==null?'—':`${Number(n).toFixed(1)}%`;
  const difference = (baseline,aiValue)=>baseline==null||aiValue==null?null:baseline-aiValue;
  const latestReviewByCase = new Map(attempts.map(attempt => [attempt.caseId, attempt]));
  const referrals = cases.filter(claim => latestReviewByCase.get(claim.id)?.finalRoute === 'Specialist Queue');
  const visibleClaims = cases.filter(claim =>
    `${claim.id} ${claim.title}`.toLowerCase().includes(search.trim().toLowerCase())
  );
  const evaluationClaimCount = evalSelected === null ? cases.length : evalSelected.length;
  const reviewSuggestions = savedRecord ? savedRecord.aiExtractedFields : ai?.extractedFields;
  const suggestionCount = Object.keys(reviewSuggestions ?? {}).length;
  const signOut = async () => {
    try {
      await axios.post(`${API}/api/logout`);
      location.href = '/login';
    } catch {
      setError('Could not sign out. Try again.');
    }
  };

  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><ShieldCheck size={27}/><div><strong>CLAIMS<span>FLOW</span></strong><small>Operations Workbench</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      {[['inbox',Inbox,'Claims inbox'],['results',BarChart3,'AI Prototype Testing'],['admin',Settings,'Administration']].map(([key,Icon,name])=><button key={key} className={`nav-item ${tab===key?'active':''}`} onClick={()=>setTab(key)}><Icon size={19}/>{name}</button>)}
      <div className="side-bottom"><span className="live-dot"/> Synthetic data only <small>Human decisions required</small></div>
    </aside>
    <main className="main">
      <header className="topbar">
        <div>
          <span className="eyebrow">INSURANCE / CLAIMS OPERATIONS</span>
          <h1>{tab==='inbox'?'Claims inbox':tab==='review'?'Claim review':tab==='results'?'AI Prototype Testing':tab==='history'?'Claim history':'Administration'}</h1>
          <p>{tab === 'inbox' ? 'Review synthetic insurance claims and save your routing decision.' : tab === 'review' ? selected?.title : ''}</p>
          {tab === 'inbox' && <p className="app-version">Version {APP_VERSION}</p>}
        </div>
        <button className="secondary" onClick={signOut}>Sign out</button>
        <div className="top-pill"><span className="live-dot"/> Prototype environment</div>
      </header>
    {error && <div className="alert error">{error}<button onClick={()=>setError('')}>Dismiss</button></div>}
    {notice && <div className="alert success">{notice}<button onClick={()=>setNotice('')}>Dismiss</button></div>}
    {tab === 'inbox' && <>
      <section className="panel inbox-guide" aria-labelledby="inbox-guide-title">
        <h2 id="inbox-guide-title">How to review a claim</h2>
        <ol>
          <li><strong>Choose a claim and a review method.</strong> For a human-only review, read the evidence and enter the details yourself. For AI-assisted review, run Gemini to fill in suggested details and a route.</li>
          <li><strong>Check the evidence and submit a route.</strong> Open the PDFs in the review. Check any suggestions against the evidence, then select the final queue. The timer starts when you open the review and can be paused.</li>
          <li><strong>Find or compare your results.</strong> Use <strong>History</strong> to reopen a saved review or download its report. Use <strong>AI Prototype Testing</strong> to run a batch comparison.</li>
        </ol>
        <p className="muted">Either method saves its own review. You can use both methods on the same claim. Compare similar claims and vary which method you use first to reduce familiarity bias.</p>
      </section>
      <div className="stats">
        <div className="stat"><Inbox/><span>Claims available</span><strong>{cases.length}</strong><small>Synthetic test cases</small></div>
        <div className="stat"><Activity/><span>Reviews submitted</span><strong>{attempts.filter(attempt => !attempt.isRevision).length}</strong><small>Human-only and AI-assisted</small></div>
        <div className="stat"><Users/><span>Specialist referrals</span><strong>{referrals.length}</strong><small>Latest saved decision</small></div>
      </div>
      <div className="section-heading">
        <h2>Claims to review</h2>
        <input className="claim-search" aria-label="Search claims" placeholder="Search by claim ID or title" value={search} onChange={e => setSearch(e.target.value)}/>
      </div>
      <div className="panel table-wrap"><table>
        <thead><tr><th>Claim</th><th>Evidence</th><th>Human-only review</th><th>AI-assisted review</th><th>Latest saved route</th><th>Saved reviews</th></tr></thead>
        <tbody>
          {visibleClaims.map(claim => {
            const reviews = attempts.filter(attempt => attempt.caseId === claim.id && !attempt.isRevision);
            const human = reviews.filter(attempt => attempt.mode === 'manual').length;
            const assisted = reviews.filter(attempt => attempt.mode === 'ai').length;
            return <tr key={claim.id}>
              <td><strong>{claim.id}</strong><small>{claim.title}</small></td>
              <td>{claim.documents.length} PDF</td>
              <td><button className="secondary" onClick={() => begin(claim, 'manual')}>{human ? 'Repeat human-only review' : 'Start human-only review'}</button><small>{human ? `${human} saved` : 'No review yet'}</small></td>
              <td><button className="primary" onClick={() => begin(claim, 'ai')}><Sparkles size={15}/>{assisted ? 'Repeat AI-assisted review' : 'Start AI-assisted review'}</button><small>{assisted ? `${assisted} saved` : 'No review yet'}</small></td>
              <td>{latestReviewByCase.get(claim.id)?.finalRoute || 'Awaiting review'}</td>
              <td><button className="secondary" onClick={() => showHistory(claim)}>History</button></td>
            </tr>;
          })}
          {!visibleClaims.length && <tr><td colSpan="6" className="empty">{claimsLoaded
            ? cases.length ? 'No claims match your search.' : 'No claims yet. Add synthetic claims in Administration.'
            : error ? 'Claims could not be loaded.' : 'Loading claims…'}</td></tr>}
        </tbody>
      </table></div>
    </>}
    {tab==='review' && selected && <><div className="review-toolbar"><button className="link" onClick={()=>{clearInterval(timer.current);setTab('inbox');}}><ArrowLeft size={16}/> Back to inbox</button><span className="mode-tag">{savedRecord?(editingRecord?'EDIT SAVED CLAIM':'SAVED CLAIM · READ ONLY'):(mode==='manual'?'MANUAL PROCESS':'AI-ASSISTED PROCESS')}</span>{savedRecord && <a className="secondary" style={{display:'inline-flex',alignItems:'center',padding:'9px 12px',textDecoration:'none',borderRadius:6}} href={`${API}/workbench/cases/${encodeURIComponent(selected.id)}/reports/${encodeURIComponent(savedRecord.id)}.pdf`} download>Download PDF report</a>}{savedRecord && <button className="secondary" onClick={()=>showHistory(selected)}><History size={15}/> Version history</button>}{savedRecord && !editingRecord && <button className="primary" onClick={()=>setEditingRecord(true)}>Edit claim</button>}{!savedRecord && <div className="timer"><Clock3 size={17}/><strong>{seconds(elapsed)}</strong><button className="secondary" onClick={toggleTimer}>{running?'Pause':'Resume'}</button></div>}</div>
      <div className="review-grid"><section className="panel evidence"><div className="panel-heading"><h2>Source evidence</h2><span>{selected.id} · {selected.documents.length} document(s)</span></div><p className="muted">{savedRecord?'These are the documents linked to this claim. Submitted values appear in the form alongside.':mode==='ai'?'Open the PDFs to check the details Gemini suggests.':'Open the PDFs and enter the claim details from the evidence.'}</p>{selected.documents.map(doc=><div className="doc" key={doc}><FileText size={18}/><div><strong>{selected.documentLabels?.[doc] || doc}</strong><small>Synthetic PDF evidence</small></div><a href={`${API}/workbench/cases/${selected.id}/documents/${encodeURIComponent(doc)}`} target="_blank" rel="noreferrer">Open PDF ↗</a></div>)}{!savedRecord && <div className="add-evidence"><strong>Add supporting PDFs</strong><input type="file" multiple accept=".pdf,application/pdf" onChange={e=>setExtraDocs(e.target.files)}/><button className="secondary" disabled={uploading||!extraDocs.length} onClick={addEvidence}>Attach to this claim</button></div>}<div className="evidence-note"><ShieldCheck size={17}/> Always verify extracted facts against the original documents.</div></section>
      <section className="panel form-panel"><div className="panel-heading"><h2>{savedRecord?'Saved claim details':mode==='manual'?'Manual claim entry':'AI-assisted claim review'}</h2><span>{savedRecord?`Version submitted ${new Date(savedRecord.submittedAt).toLocaleString()}`:mode==='manual'?'No API calls':'Human verification required'}</span></div>
      {!savedRecord && mode === 'ai' && <>
        <div className="ai-box">
          <BrainCircuit size={22}/>
          <div>
            <strong>Run Gemini API analysis</strong>
            <p>ClaimsFlow uses the configured Gemini API key to analyse the synthetic claim and its attached PDFs. Review the highlighted form values against the PDFs before submitting.</p>
            {geminiStatus?.configured === false && <p><strong>No Gemini API key is configured. This run will use local rules.</strong></p>}
          </div>
          <button className="primary" disabled={busy} onClick={processAI}>{busy ? 'Analysing claim…' : ai ? 'Run analysis again' : 'Run Gemini analysis'}</button>
        </div>
        {ai && <div className="ai-result" role="status">
          <strong>{ai.provider === 'gemini' ? 'Gemini API result' : 'Local rules fallback'}</strong>
          {ai.warning && <p>{ai.warning}</p>}
          <p>{suggestionCount
            ? `Gemini returned ${suggestionCount} of ${FIELDS.length} form fields. Check them against the PDFs and fill any gaps.`
            : 'No values were extracted. Enter claim details from the PDFs.'}</p>
          <p><strong>Suggested route:</strong> {ai.recommendedRoute}</p>
          <p>{ai.reasoning}</p>
          <small>Processing time: {ai.apiSeconds.toFixed(2)}s</small>
        </div>}
      </>}
      {GROUPS.map(([name, keys]) => <div key={name} className="field-section">
        <h3>{name}</h3>
        <div className="fields">
          {keys.map(key => {
            const suggestion = reviewSuggestions?.[key];
            const value = fields[key] ?? '';
            const corrected = suggestion !== undefined && value !== suggestion;
            const control = {
              disabled: busy || (!!savedRecord && !editingRecord),
              value,
              onChange: event => setFields({ ...fields, [key]: event.target.value }),
              placeholder: 'Enter from evidence',
              'aria-describedby': suggestion === undefined ? undefined : `suggestion-${key}`,
            };
            return <label key={key} className={key === 'description' ? 'wide' : undefined}>
              <span>{LABEL[key]}</span>
              {key === 'description' ? <textarea rows={3} {...control}/> : <input {...control}/>}
              {suggestion !== undefined && <small className="gemini-field" id={`suggestion-${key}`}>
                {corrected ? <>Gemini suggested: {suggestion}</> : 'Filled by Gemini'}
              </small>}
            </label>;
          })}
        </div>
      </div>)}
      <div className="decision"><h3>Human routing decision</h3><details className="route-guide"><summary>Understanding the five claim routes</summary><dl><dt>Fast-track</dt><dd>Simple, low-risk claim suitable for expedited handling.</dd><dt>Standard Queue</dt><dd>Routine claim requiring normal processing.</dd><dt>Specialist Queue</dt><dd>Complex claim requiring specialist expertise.</dd><dt>Manual Review</dt><dd>Missing or unclear evidence requiring further human assessment.</dd><dt>Investigation Flag</dt><dd>Inconsistencies or concerns warranting additional checks; not a finding of fraud.</dd></dl></details>{ai && <p className="muted">Suggested route: <strong>{ai.recommendedRoute}</strong>. Choose the final queue and explain any override.</p>}<label>Final queue<select disabled={!!savedRecord && !editingRecord} value={route} onChange={e=>setRoute(e.target.value)}>{ROUTES.map(r=><option key={r}>{r}</option>)}</select></label><label>Decision / override rationale<textarea disabled={!!savedRecord && !editingRecord} rows={2} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Why is this route appropriate? Required if overriding AI."/></label>{savedRecord ? <><div className="saved-meta"><strong>Original review:</strong> {savedRecord.mode==='ai'?'AI-assisted':'Manual'} · {seconds(savedRecord.elapsedSeconds)} · {savedRecord.finalRoute}{savedRecord.aiRecommendedRoute?` · AI suggested ${savedRecord.aiRecommendedRoute}`:''}<br/><strong>Record ID:</strong> {savedRecord.id}{savedRecord.basedOnAttemptId?' · Corrected version':''}</div>{editingRecord && <><p className="muted">Explain the correction in the rationale field. Saving creates a new version without overwriting the previous one. Corrections are not included in the original timing comparison.</p><button className="primary submit" disabled={busy} onClick={saveRevision}><CheckCircle2 size={18}/> Save new version</button><button className="secondary" onClick={()=>openRecord(selected,savedRecord.id)}>Cancel editing</button></>}</> : <button className="primary submit" disabled={busy || (mode==='ai'&&!ai)} onClick={submit}><CheckCircle2 size={18}/> Submit human decision & record time</button>}</div>
      </section></div></>}
    {tab==='history' && history && <><div className="section-heading"><div><h2>{history.case.id} — saved review history</h2><p>{history.case.title} · {history.case.documents.length} evidence document(s) · {history.case.status}</p></div><button className="secondary" onClick={()=>setTab('inbox')}>Back to inbox</button></div><div className="panel table-wrap"><table><thead><tr><th>SUBMITTED</th><th>METHOD</th><th>TIME</th><th>FINAL DECISION</th><th>RATIONALE</th><th>QUALITY</th><th>RECORD</th></tr></thead><tbody>{[...history.attempts].reverse().map(a=><tr key={a.id}><td>{new Date(a.submittedAt).toLocaleString()}</td><td>{a.mode}</td><td>{seconds(a.elapsedSeconds)}</td><td>{a.finalRoute}</td><td>{a.decisionReason||'Not provided'}</td><td>{a.quality?.referenceAvailable?`${a.quality.fieldAccuracy}% field match`:'Not scored'}</td><td><button className="secondary" onClick={()=>openRecord(history.case,a.id)}>View saved fields</button></td></tr>)}{!history.attempts.length&&<tr><td colSpan="7" className="empty">No saved human reviews yet.</td></tr>}</tbody></table></div><div className="info-strip"><ShieldCheck/><div><strong>Persistent local audit record</strong><p>Completed attempts retain the submitted fields, final human route, rationale, time and AI override information on the Mac mini.</p></div></div></>}
    {tab==='results' && <>
      <section className="panel evaluation-card performance-panel">
        <div className="panel-heading"><h2><BrainCircuit size={19}/> Claims evaluation</h2><span>Independent of the operational Claims Inbox</span></div>
        <p className="muted">Select claims and run an evaluation. The AI test sends each selected synthetic claim and its attached PDFs to the Gemini API using the configured key. The human simulation uses local assumptions. Measured human results come from submitted human-only reviews.</p>
        <div className="eval-selector">
          <div className="eval-selector-top"><strong>Claims available ({cases.length})</strong><input aria-label="Search evaluation claims" placeholder="Search claim ID or title" value={evalSearch} onChange={e=>setEvalSearch(e.target.value)}/></div>
          <div className="eval-selector-actions"><label><input type="checkbox" checked={cases.length>0&&(evalSelected===null||evalSelected.length===cases.length)} onChange={e=>setEvalSelected(e.target.checked?null:[])}/> Select all</label><small>{evalSelected===null?cases.length:evalSelected.length} of {cases.length} selected</small></div>
          <div className="eval-claim-list">{cases.filter(c=>`${c.id} ${c.title}`.toLowerCase().includes(evalSearch.toLowerCase())).map(c=><label key={c.id}><input type="checkbox" checked={evalSelected===null||evalSelected.includes(c.id)} onChange={e=>{const chosen=evalSelected===null?cases.map(x=>x.id):evalSelected;setEvalSelected(e.target.checked?[...new Set([...chosen,c.id])]:chosen.filter(id=>id!==c.id));}}/><strong>{c.id}</strong><span>{c.title}</span><small>{c.documents.length} PDFs</small></label>)}</div>
        </div>
        <div className="evaluation-launch"><button className="primary run-evaluation" disabled={evaluationBusy || !evaluationClaimCount} onClick={runEvaluation}>{evaluationBusy?'Running AI evaluation…':`Run Gemini evaluation · ${evaluationClaimCount} claims`}</button><div className="test-details"><strong>Evaluation scope</strong><span>Gemini extraction and routing: measured API results</span><span>Local rules are used when Gemini is unavailable.</span><span>Simulated Human: modelled time, accuracy and cost</span><span>Manual Human: submitted human-only reviews</span></div></div>
        {geminiStatus?.configured === false && <p className="muted"><strong>No Gemini API key is configured.</strong> The AI test will use local rules. An administrator can set the key under Administration.</p>}
        {evaluationError&&<p className="alert error">{evaluationError}</p>}
      </section>
      <section className="panel evaluation-card performance-panel">
        <h2>Three processing scenarios</h2>
        <div className="scenario-grid">
          <div className="scenario-card"><Sparkles size={17}/><strong>AI</strong><span>Measured processing + estimated checking</span></div>
          <div className="scenario-card"><Users size={17}/><strong>Simulated Human</strong><span>Assumption-based baseline</span></div>
          <div className="scenario-card"><Clock3 size={17}/><strong>Manual Human</strong><span>Actual submitted human-only reviews</span></div>
        </div>
        {!evaluation?<p className="muted">Run an evaluation to see the comparison. Manual results remain blank until a human completes a review.</p>:<>
          <p className="muted result-meta">Latest run: {new Date(evaluation.createdAt).toLocaleString()} · {evaluation.summary.totalCases} claims selected · {evaluation.summary.geminiSuccesses} successful Gemini results · {evaluation.summary.fallbacks} fallbacks · {evaluation.summary.errors} errors</p>
          <div className="table-wrap compact-results"><table><thead><tr><th>METRIC</th><th>AI</th><th>SIMULATED HUMAN</th><th>MANUAL HUMAN</th></tr></thead><tbody>
            <tr><td>Claims completed</td><td>{completedAI.length} / {evaluation.summary.totalCases}</td><td>{simMinutes==null?'—':evaluation.summary.totalCases}</td><td>{latestManual.length||'—'}</td></tr>
            <tr><td>Average time / claim</td><td>{fmtMin(aiTotalMinutes)}</td><td>{fmtMin(simMinutes)}</td><td>{fmtMin(manualMinutesMeasured)}</td></tr>
            <tr><td>Average cost / claim</td><td>{aiCostPerClaim==null?'—':money(aiCostPerClaim)}</td><td>{simCost==null?'—':money(simCost)}</td><td>{manualCostMeasured==null?'—':money(manualCostMeasured)}</td></tr>
            <tr><td>Field accuracy</td><td>{fmtPct(evaluation.summary.fieldAccuracy)}</td><td>{fmtPct(evaluation.summary.simulatedHumanFieldAccuracy)}</td><td>{fmtPct(mean(latestManual.filter(a=>a.quality?.referenceAvailable&&a.quality.fieldAccuracy!=null),a=>a.quality.fieldAccuracy))}</td></tr>
            <tr><td>Routing agreement</td><td>{fmtPct(evaluation.summary.routingAgreement)}</td><td>{fmtPct(evaluation.summary.simulatedHumanRoutingAgreement)}</td><td>{fmtPct(mean(latestManual.filter(a=>a.quality?.referenceAvailable&&a.quality.routeAgreement!=null),a=>a.quality.routeAgreement?100:0))}</td></tr>
            <tr><td>Total processing cost</td><td>{aiCostPerClaim==null?'—':money(aiCostPerClaim*completedAI.length)}</td><td>{simCost==null?'—':money(evaluation.cases.reduce((n,c)=>n+(c.humanSimulation?.cost||0),0))}</td><td>{latestManual.length?money(latestManual.reduce((n,a)=>n+a.elapsedSeconds/3600*runRate,0)):'—'}</td></tr>
          </tbody></table></div>
          <small className="method-note">AI time includes measured model processing plus estimated {runVerification} min checking per claim; AI cost includes estimated checking labour and {money(runApiCost)} API allowance. Simulated Human uses configured assumptions. Manual Human uses recorded review time and the same staff hourly rate. Scores only cover claims with benchmarks.</small>
          <div className="comparison-grid">
            <div className="comparison-card"><strong>AI vs Simulated Human</strong><span>{simMinutes==null?'Simulation disabled':`${completedAI.length} AI results · ${evaluation.summary.totalCases} simulated`}</span><div><span>Time difference / claim</span><b>{fmtMin(difference(simMinutes,aiTotalMinutes))}</b></div><div><span>Cost difference / claim</span><b>{simCost==null||aiCostPerClaim==null?'—':money(simCost-aiCostPerClaim)}</b></div><small>Positive = AI uses less time / cost; modelled comparison.</small></div>
            <div className="comparison-card"><strong>AI vs Manual Human</strong><span>{pairedManual.length?`${pairedManual.length} matching claims with both results`:'Awaiting completed human-only reviews on evaluated claims'}</span><div><span>Time difference / claim</span><b>{fmtMin(difference(pairedManualMinutes,pairedAIMinutes))}</b></div><div><span>Cost difference / claim</span><b>{pairedManualCost==null||pairedAICost==null?'—':money(pairedManualCost-pairedAICost)}</b></div><small>Uses matching claims only; AI checking time remains estimated.</small></div>
          </div>
        </>}
      </section>
      {evaluation&&<section className="panel evaluation-card performance-panel">
        <h2><PoundSterling size={18}/> Business value projection</h2>
        <p className="muted">Uses the same AI and simulated-human per-claim costs above. This is a staff-capacity value projection, not realised cash savings.</p>
        <div className="projection-controls"><label>Claims per month<input type="number" min="0" step="100" value={monthlyClaims} onChange={e=>setMonthlyClaims(e.target.value)}/></label><div><small>AI vs Simulated Human · monthly</small><strong>{simCost==null||aiCostPerClaim==null?'—':money((simCost-aiCostPerClaim)*Number(monthlyClaims))}</strong></div><div><small>AI vs Simulated Human · annually</small><strong>{simCost==null||aiCostPerClaim==null?'—':money((simCost-aiCostPerClaim)*Number(monthlyClaims)*12)}</strong></div></div>
        <small className="method-note">AI vs Manual Human projection: {pairedManual.length?`${money((pairedManualCost-pairedAICost)*Number(monthlyClaims))} per month based on ${pairedManual.length} matching claim(s)`:'— until matching manual reviews exist'}. Excludes implementation, licensing, governance, rework and infrastructure.</small>
      </section>}
      {evaluation&&<details className="panel evaluation-card performance-panel"><summary>Detailed AI test results</summary><p className="muted">Only fully successful AI calls count towards AI accuracy. Missing benchmarks are unscored.</p><div className="table-wrap compact-results"><table><thead><tr><th>CLAIM</th><th>STATUS</th><th>FIELDS</th><th>EXPECTED ROUTE</th><th>AI ROUTE</th><th>MATCH</th><th>AI TIME</th></tr></thead><tbody>{evaluation.cases.map(c=><tr key={c.caseId}><td>{c.caseId}</td><td>{c.status}</td><td>{c.fieldAccuracy==null?'—':`${c.fieldAccuracy}%`}</td><td>{c.expectedRoute||'—'}</td><td>{c.recommendedRoute||'—'}</td><td>{c.routeAgreement==null?'—':c.routeAgreement?'Yes':'No'}</td><td>{c.apiSeconds==null?'—':`${c.apiSeconds}s`}</td></tr>)}</tbody></table></div></details>}
      <details className="panel evaluation-card performance-panel"><summary>Human review audit log</summary><div className="table-wrap compact-results"><table><thead><tr><th>CLAIM</th><th>METHOD</th><th>TIME</th><th>COST</th><th>FINAL ROUTE</th><th>OVERRIDDEN</th></tr></thead><tbody>{[...attempts].reverse().map(a=><tr key={a.id}><td>{a.caseId}</td><td>{a.mode==='ai'?'AI-assisted':'Manual Human'}</td><td>{seconds(a.elapsedSeconds)}</td><td>{money(a.elapsedSeconds/3600*Number(hourlyRate)+(a.mode==='ai'?Number(apiCost):0))}</td><td>{a.finalRoute}</td><td>{a.overridden?'Yes':a.mode==='ai'?'No':'—'}</td></tr>)}{!attempts.length&&<tr><td colSpan="6" className="empty">No submitted human reviews.</td></tr>}</tbody></table></div></details>
    </>}
    {tab==='admin' && <>
      {me?.username && <section className="panel admin-panel">
        <h2><a href="/account">Account settings</a></h2>
        <p className="muted">Signed in as {me.username}</p>
      </section>}
      {me?.role==='admin' && <section className="panel admin-panel"><h2>Gemini API connection</h2><p className="muted">The API key authenticates AI-assisted claim reviews and batch evaluations. ClaimsFlow stores the key in the host Mac’s login Keychain. Save the key, then test the connection before running an evaluation.</p><p><strong>Status: {geminiStatus?.configured?'Key configured':'Key not configured'}</strong></p><div className="gemini-setup"><input type="password" autoComplete="off" spellCheck="false" aria-label="Gemini API key" placeholder="Paste your Gemini API key" value={geminiKey} onChange={e=>setGeminiKey(e.target.value)}/><button className="primary" disabled={geminiSaving||!geminiKey.trim()} onClick={saveGeminiKey}>{geminiSaving?'Saving…':'Save Gemini key'}</button></div>{geminiMessage&&<p className="muted" role="status">{geminiMessage}</p>}<button className="primary" disabled={geminiTesting||!geminiStatus?.configured} onClick={testGemini}>{geminiTesting?"Testing Gemini…":"Test Gemini Connection"}</button>{geminiTestResult&&<p role="status" style={{overflowWrap:"anywhere"}}><strong>{geminiTestResult.ok?"Connected successfully":"Connection failed"}:</strong> {geminiTestResult.message}</p>}<p className="muted">The test sends a short request to Gemini and reports API errors without displaying your saved key.</p></section>}

      <div className="section-heading"><div><h2>Manage synthetic claims</h2><p>Administration tools for setting up a larger test inbox. Use fictional information only.</p></div></div>
      <section className="panel admin-panel"><h2>Bulk import claims</h2><p className="muted">Upload a ZIP with one folder per claim, containing 1–8 text-based PDFs. Optionally add a manifest.csv with columns <code>folder,title</code>. Maximum 100 claims, 100 MB compressed. Import is validated before claims are added.</p><input aria-label="Bulk claim ZIP" type="file" accept=".zip,application/zip" onChange={e=>setBulkFile(e.target.files?.[0]||null)}/><button className="primary" disabled={!bulkFile||bulkBusy} onClick={importBulk}>{bulkBusy?'Importing…':'Import claims ZIP'}</button>
      <details><summary>Example ZIP structure</summary><pre>{`claims.zip\n  manifest.csv\n  claim_001/\n    incident.pdf\n    supporting.pdf\n  claim_002/\n    incident.pdf\n\nmanifest.csv:\nfolder,title\nclaim_001,Rear-end collision\nclaim_002,Theft claim`}</pre></details></section>
      <section className="panel admin-panel"><h2>Add one synthetic claim</h2><p className="muted">Upload 1–8 text-based PDF documents for a fictional claim.</p><input placeholder="Fictional claim title" value={newTitle} onChange={e=>setNewTitle(e.target.value)}/><input type="file" multiple accept=".pdf,application/pdf" onChange={e=>setNewDocs(e.target.files)}/><button className="primary" disabled={uploading} onClick={uploadCase}>{uploading?'Uploading…':'Create claim'}</button></section>
      <section className="panel admin-panel"><h2>Human review simulation settings</h2><p className="muted">Used only for the optional automated baseline on Performance. These are illustrative assumptions, not measured staff results.</p><label><input type="checkbox" checked={simulateHuman} onChange={e=>setSimulateHuman(e.target.checked)}/> <span>Include simulated human baseline</span></label><div className="cost-inputs"><label>Base handling time (minutes)<input type="number" min="0" max="120" value={manualMinutes} onChange={e=>setManualMinutes(e.target.value)}/></label><label>Time per evidence document (minutes)<input type="number" min="0" max="60" step="0.5" value={documentMinutes} onChange={e=>setDocumentMinutes(e.target.value)}/></label><label>Assessment time (minutes)<input type="number" min="0" max="60" step="0.5" value={complexityMinutes} onChange={e=>setComplexityMinutes(e.target.value)}/></label><label>Assumed field error rate (%)<input type="number" min="0" max="50" value={humanErrorRate} onChange={e=>setHumanErrorRate(e.target.value)}/></label><label>Assumed routing error rate (%)<input type="number" min="0" max="50" value={humanRoutingErrorRate} onChange={e=>setHumanRoutingErrorRate(e.target.value)}/></label><label>Staff cost (£ per hour)<input type="number" min="0" value={hourlyRate} onChange={e=>setHourlyRate(e.target.value)}/></label><label>AI checking time (minutes)<input type="number" min="0" max="120" step="0.5" value={verificationMinutes} onChange={e=>setVerificationMinutes(e.target.value)}/></label><label>AI API cost allowance (£ / claim)<input type="number" min="0" step="0.01" value={apiCost} onChange={e=>setApiCost(e.target.value)}/></label></div></section>
      {me?.role==='admin' && <section className="panel admin-panel"><h2>Reset demonstration</h2><p className="muted">Resets the local test records. This is destructive; export any results you need first.</p><button className="secondary" onClick={reset}><RotateCcw size={15}/> Reset demo</button></section>}
    </>}
    </main></div>;
}
