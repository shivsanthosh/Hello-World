import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { CHECKS } from '../engine.js';
import { statusFor } from '../flow.js';

function SummaryBody({ r }) {
  return (
    <ul className="dcr-list">
      {CHECKS.map((c) => {
        const e = r.envelope[c.id];
        const st = e ? statusFor(e.dcr) : { kind: 'info' };
        const w = e ? Math.min(e.dcr, 1.5) / 1.5 : 0;
        return (
          <li key={c.id} className={`k-${st.kind}`}>
            <span className="dl">{c.label}</span>
            <span className="bar-track"><span className="bar-fill" style={{ width: `${w * 100}%` }} /><span className="bar-one" /></span>
            <span className="dv">{e ? e.dcr.toFixed(2) : '—'}</span>
          </li>
        );
      })}
    </ul>
  );
}

function StepNode({ data }) {
  const { step, r, units, active } = data;
  const st = step.summary
    ? r.governing ? statusFor(r.governing.dcr) : { kind: 'info', text: '—' }
    : step.status(r);
  const metrics = step.summary ? [] : step.metrics(r, units);
  return (
    <div className={`step k-${st.kind}${active ? ' active' : ''}${step.asce || step.change ? ' changed' : ''}`}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="step-head">
        <span className="code">{step.id}</span>
        <span className="title">{step.title}</span>
        <span className={`pill p-${st.kind}`}>{st.text}</span>
      </div>
      <div className="refs">
        <span>CIB {step.cib}</span>
        {step.asce && <span className="asce">ASCE 7-22 {step.asce}</span>}
      </div>
      {step.summary ? (
        <SummaryBody r={r} />
      ) : (
        <dl className="metrics">
          {metrics.map(([k, v]) => (
            <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
          ))}
        </dl>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}
export default memo(StepNode);
