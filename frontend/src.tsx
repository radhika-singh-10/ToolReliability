import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

type CaseResult = {scenario_id:string; scenario_name:string; status:string; scores:{overall:number}; failures:string[]};
type Run = {run_id:string; agent:string; total:number; passed:number; pass_rate:number; average_score:number; p95_latency_ms:number; cost_per_success:number; results:CaseResult[]};

function App(){
  const [run,setRun]=useState<Run|null>(null); const [loading,setLoading]=useState(false); const [agent,setAgent]=useState('reference');
  async function execute(){setLoading(true); const r=await fetch(`http://localhost:8000/api/runs?agent=${agent}`,{method:'POST'}); setRun(await r.json()); setLoading(false)}
  return <main><header><div><span className="eyebrow">AGENT EVALUATION PLATFORM</span><h1>ToolReliability</h1><p>Catch tool-use regressions before they reach production.</p></div><div className="control"><select value={agent} onChange={e=>setAgent(e.target.value)}><option value="reference">Reference agent</option><option value="regression">Regression demo</option></select><button onClick={execute} disabled={loading}>{loading?'Running…':'Run evaluation'}</button></div></header>
  {!run?<section className="empty"><div className="pulse">✓</div><h2>Ready to evaluate</h2><p>Run the commerce suite across tool selection, arguments, sequence, state and recovery.</p></section>:<><section className="metrics"><Card label="Pass rate" value={`${(run.pass_rate*100).toFixed(0)}%`}/><Card label="Average score" value={run.average_score.toFixed(3)}/><Card label="P95 latency" value={`${run.p95_latency_ms} ms`}/><Card label="Cost / success" value={`$${run.cost_per_success.toFixed(4)}`}/></section><section className="panel"><h2>Scenario results</h2>{run.results.map(x=><div className="row" key={x.scenario_id}><span className={`status ${x.status}`}>{x.status==='passed'?'PASS':'FAIL'}</span><div><strong>{x.scenario_name}</strong><small>{x.failures.join(' · ')||'All checks satisfied'}</small></div><b>{x.scores.overall.toFixed(3)}</b></div>)}</section></>}
  </main>
}
function Card({label,value}:{label:string,value:string}){return <article><small>{label}</small><strong>{value}</strong></article>}
createRoot(document.getElementById('root')!).render(<App/>);

