import { useEffect, useRef, useState } from 'react';
import { CHECKS } from './engine.js';
import { statusFor } from './flow.js';
import { fromDisplay, round, unit, fmt } from './units.js';

function NumberField({ id, def, value, units, onChange }) {
  const shown = round(value, def.dim, units);
  const [draft, setDraft] = useState(String(shown));
  const focused = useRef(false);
  useEffect(() => {
    if (!focused.current) setDraft(String(shown));
  }, [shown]);
  return (
    <input
      id={id}
      type="number"
      inputMode="decimal"
      step="any"
      value={draft}
      onFocus={() => (focused.current = true)}
      onBlur={() => {
        focused.current = false;
        setDraft(String(round(value, def.dim, units)));
      }}
      onChange={(e) => {
        setDraft(e.target.value);
        const n = parseFloat(e.target.value);
        if (Number.isFinite(n)) onChange(def.dim === 'int' ? Math.round(n) : fromDisplay(n, def.dim, units));
      }}
    />
  );
}

function Field({ k, def, inputs, units, setField }) {
  const id = `f-${k}`;
  const value = inputs[k];
  let control;
  if (def.type === 'select') {
    control = (
      <select id={id} value={String(value)} onChange={(e) => setField(k, def.numeric ? Number(e.target.value) : e.target.value)}>
        {def.options.map(([v, l]) => (
          <option key={v} value={String(v)}>{l}</option>
        ))}
      </select>
    );
  } else if (def.type === 'bool') {
    control = <input id={id} type="checkbox" checked={!!value} onChange={(e) => setField(k, e.target.checked)} />;
  } else {
    control = <NumberField id={id} def={def} value={value} units={units} onChange={(v) => setField(k, v)} />;
  }
  const u = def.dim ? unit(def.dim, units) : '';
  return (
    <div className={`field${def.type === 'bool' ? ' field-bool' : ''}`}>
      <label htmlFor={id}>{def.label}</label>
      <div className="control">
        {control}
        {u && <span className="u">{u}</span>}
      </div>
      {def.help && <p className="help">{def.help}</p>}
    </div>
  );
}

function ComboTable({ r, set, onJump }) {
  const rows = r.rows.filter((x) => x.set === set);
  if (!rows.length) return <p className="muted">Not used for this system.</p>;
  return (
    <div className="table-wrap">
      <table className="combo">
        <thead>
          <tr><th>ID</th><th>Combination</th><th>Max DCR</th><th>Check</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const entries = Object.entries(row.checks).filter(([, c]) => c);
            const [ck, cv] = entries.reduce((m, e) => (!m || e[1].dcr > m[1].dcr ? e : m), null) || [];
            const st = cv ? statusFor(cv.dcr) : { kind: 'info' };
            const ch = CHECKS.find((c) => c.id === ck);
            return (
              <tr key={row.id}>
                <td className="mono">{row.id}</td>
                <td>{row.name}</td>
                <td className={`mono k-${st.kind}`}>{cv ? cv.dcr.toFixed(2) : '—'}</td>
                <td>{ch ? <button className="link" onClick={() => onJump(ch.node)}>{ch.label}</button> : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CheckTable({ r, check, dim, units }) {
  const rows = r.rows
    .filter((x) => x.checks[check])
    .map((x) => ({ ...x.checks[check], id: x.id, name: x.name, set: x.set }))
    .sort((a, b) => b.dcr - a.dcr)
    .slice(0, 8);
  if (!rows.length) return <p className="muted">This check does not apply to the current static system.</p>;
  const setName = { U: 'LRFD', A: 'ASD', S: 'Service' };
  return (
    <div className="table-wrap">
      <table className="combo">
        <thead>
          <tr><th>ID</th><th>Set</th><th>Demand</th><th>Capacity</th><th>DCR</th></tr>
        </thead>
        <tbody>
          {rows.map((x) => {
            const st = statusFor(x.dcr);
            return (
              <tr key={x.id} title={x.name + (x.note ? ` · ${x.note}` : '')}>
                <td className="mono">{x.id}</td>
                <td>{setName[x.set]}</td>
                <td className="mono">{fmt(x.demand, dim, units)}</td>
                <td className="mono">{fmt(x.cap, dim, units)}</td>
                <td className={`mono k-${st.kind}`}>{x.dcr.toFixed(2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Verdict({ r, onJump }) {
  return (
    <div className="verdict-list">
      {CHECKS.map((c) => {
        const e = r.envelope[c.id];
        const st = e ? statusFor(e.dcr) : { kind: 'info', text: 'n/a' };
        return (
          <button key={c.id} className={`vrow k-${st.kind}`} onClick={() => onJump(c.node)}>
            <span className="mono">{c.node}</span>
            <span>{c.label}</span>
            <span className="mono">{e ? e.dcr.toFixed(2) : '—'}</span>
            <span className="vgov">{e ? `${e.combo}: ${e.comboName}` : 'Not applicable'}</span>
          </button>
        );
      })}
    </div>
  );
}

export default function Inspector({ step, r, inputs, units, setField, fields, onClose, onJump }) {
  const st = step.summary ? (r.governing ? statusFor(r.governing.dcr) : { kind: 'info', text: '—' }) : step.status(r);
  const filter = step.fieldsFilter ? step.fieldsFilter(inputs) : () => true;
  const keys = (step.fields || []).filter(filter);
  const metrics = step.summary ? [] : step.metrics(r, units);
  return (
    <aside className="inspector" aria-label={`${step.title} details`}>
      <div className="ins-head">
        <div>
          <div className="ins-code">{step.id} · CIB {step.cib}{step.asce ? ` · ASCE 7-22 ${step.asce}` : ''}</div>
          <h2>{step.title}</h2>
        </div>
        <span className={`pill p-${st.kind}`}>{st.text}</span>
        <button className="close" onClick={onClose} aria-label="Close details">×</button>
      </div>
      <div className="ins-body">
        <p className="about">{step.about}</p>
        {step.change && (
          <div className="change">
            <div className="change-label">Eurocode → ASCE 7-22</div>
            <p>{step.change}</p>
          </div>
        )}
        {step.summary && <Verdict r={r} onJump={onJump} />}
        {metrics.length > 0 && (
          <section>
            <h3>Results</h3>
            <dl className="metrics wide">
              {metrics.map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
              ))}
            </dl>
          </section>
        )}
        {keys.length > 0 && (
          <section>
            <h3>Inputs</h3>
            <div className="fields">
              {keys.map((k) => (
                <Field key={k} k={k} def={fields[k]} inputs={inputs} units={units} setField={setField} />
              ))}
            </div>
          </section>
        )}
        {step.combos && (
          <section>
            <h3>Combinations</h3>
            <ComboTable r={r} set={step.combos} onJump={onJump} />
          </section>
        )}
        {step.check && (
          <section>
            <h3>Worst combinations</h3>
            <CheckTable r={r} check={step.check} dim={step.dim} units={units} />
          </section>
        )}
        {step.eqs && (
          <section>
            <h3>Equations</h3>
            <ul className="eqs">
              {step.eqs.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </section>
        )}
        {step.summary && (
          <p className="fine">
            ASCE 7-22 sets loads only. The resistance side keeps the CIB model, with φ = 1/γ_M from CIB Table 2.5. The load mapping (temperature factors, 0.42W for service, ASD combinations for support stresses) is engineering judgment. Check it against the building code and the panel manufacturer's evaluation report before using the results for design.
          </p>
        )}
      </div>
    </aside>
  );
}
