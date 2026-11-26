import { useCallback, useEffect, useMemo, useState } from 'react';
import { ReactFlow, Background, Controls, MiniMap, ReactFlowProvider, useReactFlow } from '@xyflow/react';
import { design, DEFAULT_INPUTS, CORE_PRESETS, CHECKS } from './engine.js';
import { STEPS, EDGES, LANES, FIELDS, statusFor } from './flow.js';
import StepNode from './nodes/StepNode.jsx';
import LaneNode from './nodes/LaneNode.jsx';
import Inspector from './Inspector.jsx';

const COL_W = 316;
const NODE_W = 252;
const ROW_H = 178;
const TOP = 84;

const nodeTypes = { step: StepNode, lane: LaneNode };

function useDesign(inputs) {
  return useMemo(() => {
    const r = design(inputs);
    const uRows = r.rows.filter((x) => x.set === 'U');
    const rowMax = (row) => Math.max(0, ...Object.values(row.checks).filter(Boolean).map((c) => c.dcr));
    const gU = uRows.reduce((m, x) => (!m || rowMax(x) > rowMax(m) ? x : m), null);
    r.governingU = gU ? `${gU.id}: ${gU.name}` : null;
    r.maxRow = uRows.reduce((m, x) => (!m || Math.max(Math.abs(x.a.Mmax), Math.abs(x.a.MB), Math.abs(x.a.Mmin)) > Math.max(Math.abs(m.a.Mmax), Math.abs(m.a.MB), Math.abs(m.a.Mmin)) ? x : m), null);
    r.rowMax = rowMax;
    return r;
  }, [inputs]);
}

function Flow() {
  const [inputs, setInputs] = useState(DEFAULT_INPUTS);
  const [units, setUnits] = useState('us');
  const [selected, setSelected] = useState('F1');
  const r = useDesign(inputs);
  const { fitView } = useReactFlow();

  const maxRows = Math.max(...STEPS.map((s) => s.row)) + 1;
  const laneH = TOP + maxRows * ROW_H + 8;

  const nodes = useMemo(() => {
    const lanes = LANES.map((l) => ({
      id: `lane-${l.id}`,
      type: 'lane',
      position: { x: l.x * COL_W - 20, y: 0 },
      data: { lane: l },
      style: { width: NODE_W + 40, height: laneH },
      selectable: false,
      draggable: false,
      focusable: false,
      zIndex: -1,
    }));
    const steps = STEPS.map((s) => {
      const lane = LANES.find((l) => l.id === s.lane);
      const rowY = s.summary ? 2 : s.row;
      return {
        id: s.id,
        type: 'step',
        position: { x: lane.x * COL_W, y: TOP + rowY * ROW_H },
        data: { step: s, r, units, active: selected === s.id },
        style: { width: NODE_W },
        draggable: false,
      };
    });
    return [...lanes, ...steps];
  }, [r, units, selected, laneH]);

  const edges = useMemo(() => {
    const statusOf = (id) => {
      const s = STEPS.find((x) => x.id === id);
      return s?.status ? s.status(r).kind : 'info';
    };
    return EDGES.map(([a, b]) => {
      const kind = b === 'F1' ? statusOf(a) : 'info';
      const hot = selected === a || selected === b;
      return {
        id: `${a}-${b}`,
        source: a,
        target: b,
        type: 'smoothstep',
        animated: hot,
        className: `edge edge-${kind}${hot ? ' edge-hot' : ''}`,
      };
    });
  }, [r, selected]);

  const setField = useCallback((key, value) => {
    setInputs((prev) => {
      if (key === 'core') return { ...prev, core: value, ...CORE_PRESETS[value], label: undefined };
      if (key === 'app') {
        const next = { ...prev, app: value };
        if (value === 'wall' && prev.app !== 'wall') next.L = Math.max(prev.L, 4.0);
        return next;
      }
      return { ...prev, [key]: value };
    });
  }, []);

  useEffect(() => {
    const t = setTimeout(() => fitView({ padding: 0.06, duration: 0 }), 30);
    return () => clearTimeout(t);
  }, [fitView]);

  const step = STEPS.find((s) => s.id === selected);
  const verdict = r.governing ? statusFor(r.governing.dcr) : { kind: 'info', text: '—' };
  const govLabel = r.governing ? CHECKS.find((c) => c.id === r.governing.check)?.label : '';

  return (
    <div className="app">
      <header className="bar">
        <div className="brand">
          <span className="section-mark" aria-hidden="true"><i /><i /><i /></span>
          <div>
            <h1>Sandwich Panel Design Flow</h1>
            <p>CIB Publication 257 resistance model · ASCE 7-22 loads and combinations</p>
          </div>
        </div>
        <div className="bar-controls">
          <div className="seg" role="group" aria-label="Application">
            {[['roof', 'Roof'], ['wall', 'Wall']].map(([v, l]) => (
              <button key={v} id={`app-${v}`} className={inputs.app === v ? 'on' : ''} onClick={() => setField('app', v)}>{l}</button>
            ))}
          </div>
          <div className="seg" role="group" aria-label="Units">
            {[['us', 'US'], ['si', 'SI']].map(([v, l]) => (
              <button key={v} id={`units-${v}`} className={units === v ? 'on' : ''} onClick={() => setUnits(v)}>{l}</button>
            ))}
          </div>
          <button className={`verdict v-${verdict.kind}`} onClick={() => setSelected('F1')} title="Open the design verdict">
            <span className="v-dot" />
            <span>{verdict.kind === 'fail' ? 'Fails' : verdict.kind === 'warn' ? 'Near limit' : 'Passes'}</span>
            <span className="v-dcr">{verdict.text}</span>
            <span className="v-gov">{govLabel}</span>
          </button>
          <button className="ghost" id="reset" onClick={() => setInputs(DEFAULT_INPUTS)} title="Restore the example inputs">Reset example</button>
        </div>
      </header>
      <div className="body">
        <div className="canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, n) => n.type === 'step' && setSelected(n.id)}
            nodesConnectable={false}
            elementsSelectable
            minZoom={0.2}
            maxZoom={1.6}
            proOptions={{ hideAttribution: false }}
          >
            <Background gap={24} size={1} className="bg-dots" />
            <Controls showInteractive={false} position="bottom-left" />
            <MiniMap pannable zoomable position="top-right" style={{ width: 150, height: 96 }} className="minimap" nodeClassName={(n) => (n.type === 'lane' ? 'mm-lane' : `mm-${n.data.step.status ? n.data.step.status(r).kind : 'info'}`)} />
          </ReactFlow>
          <div className="example-tag">Example inputs, replace with your project values</div>
        </div>
        {step && (
          <Inspector key={step.id} step={step} r={r} inputs={inputs} units={units} setField={setField} fields={FIELDS} onClose={() => setSelected(null)} onJump={setSelected} />
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <Flow />
    </ReactFlowProvider>
  );
}
