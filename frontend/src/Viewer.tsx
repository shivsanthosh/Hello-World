/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

type Props = { walls: any[]; products: any[]; sections: any[]; selected: number | null; onSelect: (id: number) => void }

function label(text: string, size = 0.42) {
  const c = document.createElement('canvas'); const ctx = c.getContext('2d')!
  ctx.font = '600 44px system-ui'; c.width = Math.ceil(ctx.measureText(text).width) + 24; c.height = 60
  ctx.font = '600 44px system-ui'; ctx.fillStyle = 'rgba(255,255,255,.88)'; ctx.fillRect(0, 0, c.width, c.height)
  ctx.fillStyle = '#18212f'; ctx.fillText(text, 12, 45)
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false }))
  s.scale.set(size * c.width / c.height, size, 1); s.renderOrder = 10
  return s
}

/** Builds one wall in local coordinates: x along wall, y up, +z outward. */
function buildWall(w: any, product: any, section: any, outSign: number, opts: { zones: boolean; elevation: boolean; selected: boolean; text: number }) {
  const g = new THREE.Group()
  const L = w.length_m, H = w.height_m, t = (product?.thickness_mm ?? 100) / 1000
  const shape = new THREE.Shape([new THREE.Vector2(0, 0), new THREE.Vector2(L, 0), new THREE.Vector2(L, H), new THREE.Vector2(0, H)])
  for (const o of w.openings) {
    const h = new THREE.Path()
    h.moveTo(o.offset_m, o.sill_m); h.lineTo(o.offset_m + o.width_m, o.sill_m)
    h.lineTo(o.offset_m + o.width_m, o.sill_m + o.height_m); h.lineTo(o.offset_m, o.sill_m + o.height_m); h.closePath()
    shape.holes.push(h)
  }
  const st = w.latest_run?.current ? w.latest_run.status : 'NONE'
  const col = st === 'PASS' ? 0x9fc7ad : st === 'FAIL' ? 0xe19a94 : 0xb9c4d2
  const panel = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: t, bevelEnabled: false }),
    new THREE.MeshStandardMaterial({ color: col, metalness: 0.35, roughness: 0.55, transparent: opts.elevation, opacity: opts.elevation ? 0.45 : 1,
      emissive: opts.selected ? 0x1d4f8a : 0x000000, emissiveIntensity: opts.selected ? 0.35 : 0 }))
  panel.position.z = outSign > 0 ? 0 : -t
  panel.userData.wallId = w.id
  g.add(panel)
  const zOut = outSign * (t + 0.005), zIn = outSign > 0 ? 0 : 0
  // panel joints at each module
  const mod = (product?.module_mm ?? 1000) / 1000, pts: number[] = []
  for (let x = mod; x < L - 1e-6; x += mod) pts.push(x, 0, zOut, x, H, zOut)
  const jg = new THREE.BufferGeometry(); jg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
  g.add(new THREE.LineSegments(jg, new THREE.LineBasicMaterial({ color: 0x5d6b7e, transparent: true, opacity: 0.55 })))
  // girts (cut at openings they cross) on the inside face
  const d = (section?.depth_mm ?? 200) / 1000, n = w.n_spans, gm = new THREE.MeshStandardMaterial({ color: 0xc2410c, metalness: 0.5, roughness: 0.5 })
  for (let k = 1; k <= n; k++) {
    const z = Math.min((H / n) * k, H - 0.04)
    let segs: [number, number][] = [[0, L]]
    for (const o of w.openings) if (o.sill_m < (H / n) * k && (H / n) * k < o.sill_m + o.height_m) {
      segs = segs.flatMap(([a, b]) => { const r: [number, number][] = []
        if (o.offset_m > a) r.push([a, Math.min(b, o.offset_m)]); if (o.offset_m + o.width_m < b) r.push([Math.max(a, o.offset_m + o.width_m), b]); return r.filter(([p, q]) => q > p) })
    }
    for (const [a, b] of segs) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(b - a, 0.07, d), gm)
      m.position.set((a + b) / 2, z, zIn - outSign * d / 2); g.add(m)
    }
    if (opts.elevation) { const ts = Math.min(opts.text * 0.8, (H / n) * 0.85), s = label(`${((H / n) * k).toFixed(2)} m`, ts); s.position.set(-ts * 2.2, (H / n) * k, zOut); g.add(s) }
  }
  // opening framing
  const fm = new THREE.LineBasicMaterial({ color: 0x7c2d12 })
  for (const o of w.openings) {
    const a = o.offset_m, b = a + o.width_m, s = o.sill_m, e = s + o.height_m
    const fg = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(a, s, zOut), new THREE.Vector3(a, e, zOut), new THREE.Vector3(b, e, zOut), new THREE.Vector3(b, s, zOut), new THREE.Vector3(a, s, zOut)])
    g.add(new THREE.Line(fg, fm))
  }
  // columns at bay lines
  const cm = new THREE.MeshStandardMaterial({ color: 0x475569 })
  for (const x of w.bay_offsets_m) { const c = new THREE.Mesh(new THREE.BoxGeometry(0.25, H, 0.25), cm); c.position.set(x, H / 2, -outSign * (d + 0.125)); g.add(c) }
  // end zones
  const zw = w.latest_run?.end_zone_width_m
  if (opts.zones && zw) for (const x0 of [0, L - zw]) {
    const z = new THREE.Mesh(new THREE.PlaneGeometry(zw, H), new THREE.MeshBasicMaterial({ color: 0xf59e0b, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false }))
    z.position.set(x0 + zw / 2, H / 2, outSign * (t + 0.02)); g.add(z)
  }
  if (opts.elevation) {
    const T = opts.text
    const a = label(`L = ${L.toFixed(2)} m`, T); a.position.set(L / 2, -T * 1.2, zOut); g.add(a)
    const b = label(`H = ${H.toFixed(2)} m`, T); b.position.set(L + T * 3.6, H / 2, zOut); g.add(b)
    const c = label(`${w.name} — ${n} girt lines @ ${(H / n).toFixed(3)} m, column bay ${w.max_bay_m.toFixed(2)} m`, T); c.position.set(L / 2, H + T * 1.3, zOut); g.add(c)
  }
  return g
}

export default function Viewer({ walls, products, sections, selected, onSelect }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const ctx = useRef<any>(null)
  const [mode, setMode] = useState<'3d' | 'elevation'>('3d')
  const [zones, setZones] = useState(true)
  const onSel = useRef(onSelect); onSel.current = onSelect

  useEffect(() => {
    const el = host.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene(); scene.background = new THREE.Color(0xe8eef5)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.1))
    const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(40, 60, 30); scene.add(sun)
    const persp = new THREE.PerspectiveCamera(45, 1, 0.1, 2000)
    const ortho = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 2000)
    const controls = new OrbitControls(persp, renderer.domElement)
    const root = new THREE.Group(); scene.add(root)
    const c = { renderer, scene, persp, ortho, controls, root, camera: persp as THREE.Camera, raf: 0, framed: '' }
    ctx.current = c
    const resize = () => { const w = el.clientWidth, h = el.clientHeight; renderer.setSize(w, h); persp.aspect = w / h; persp.updateProjectionMatrix() }
    resize(); const ro = new ResizeObserver(resize); ro.observe(el)
    const loop = () => { c.raf = requestAnimationFrame(loop); controls.update(); renderer.render(scene, c.camera) }; loop()
    let down = [0, 0]
    const pd = (e: PointerEvent) => { down = [e.clientX, e.clientY] }
    const pu = (e: PointerEvent) => {
      if (Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return
      const r = renderer.domElement.getBoundingClientRect()
      const p = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      const rc = new THREE.Raycaster(); rc.setFromCamera(p, c.camera)
      const hit = rc.intersectObjects(root.children, true).find(h => h.object.userData.wallId)
      if (hit) onSel.current(hit.object.userData.wallId)
    }
    renderer.domElement.addEventListener('pointerdown', pd); renderer.domElement.addEventListener('pointerup', pu)
    return () => { cancelAnimationFrame(c.raf); ro.disconnect(); controls.dispose(); renderer.dispose(); el.removeChild(renderer.domElement) }
  }, [])

  useEffect(() => {
    const c = ctx.current; if (!c) return
    c.root.traverse((o: any) => { o.geometry?.dispose?.(); if (o.material) { o.material.map?.dispose?.(); o.material.dispose?.() } })
    c.root.clear()
    if (!walls.length) return
    const xs = walls.flatMap(w => [w.start_x, w.end_x]), ys = walls.flatMap(w => [w.start_y, w.end_y])
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2
    const hmax = Math.max(...walls.map(w => w.height_m)), span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 10)
    const elev = mode === 'elevation' && selected != null
    let selInfo: any = null
    for (const w of walls) {
      if (elev && w.id !== selected) continue
      const ux = (w.end_x - w.start_x) / w.length_m, uy = (w.end_y - w.start_y) / w.length_m
      const mx = (w.start_x + w.end_x) / 2 - cx, my = (w.start_y + w.end_y) / 2 - cy
      const outSign = (uy * mx - ux * my) >= 0 ? 1 : -1          // right-hand normal (uy,-ux) points away from centroid?
      const g = buildWall(w, products.find(p => p.id === w.product_id), sections.find(s => s.id === w.section_id), outSign,
        { zones, elevation: elev, selected: w.id === selected && !elev, text: Math.max(w.length_m, w.height_m * 1.6) / 42 })
      g.position.set(w.start_x - cx, w.base_elev_m, -(w.start_y - cy)); g.rotation.y = Math.atan2(uy, ux)
      c.root.add(g)
      if (w.id === selected) selInfo = { w, n: new THREE.Vector3(uy * outSign, 0, ux * outSign), mid: new THREE.Vector3(mx, w.height_m / 2, -my) }
    }
    if (!elev) {
      const slab = new THREE.Mesh(new THREE.BoxGeometry(Math.max(...xs) - Math.min(...xs) + 2, 0.2, Math.max(...ys) - Math.min(...ys) + 2), new THREE.MeshStandardMaterial({ color: 0xcfd6df }))
      slab.position.y = -0.1; c.root.add(slab)
      const grid = new THREE.GridHelper(span * 3, 30, 0x9aa8b8, 0xc8d1dc); grid.position.y = -0.21; c.root.add(grid)
    }
    const key = `${mode}:${elev ? selected : ''}:${walls.length}`
    if (elev && selInfo) {
      const { w, n, mid } = selInfo
      const el = host.current!, asp = el.clientWidth / el.clientHeight
      const T = Math.max(w.length_m, w.height_m * 1.6) / 42, halfW = Math.max((w.length_m + T * 16) / 2, ((w.height_m + T * 6) / 2) * asp)
      c.ortho.left = -halfW; c.ortho.right = halfW; c.ortho.top = halfW / asp; c.ortho.bottom = -halfW / asp; c.ortho.updateProjectionMatrix()
      c.ortho.position.copy(mid.clone().add(n.clone().multiplyScalar(200))); c.ortho.lookAt(mid)
      c.camera = c.ortho; c.controls.enabled = false
    } else {
      c.camera = c.persp; c.controls.enabled = true
      if (c.framed !== key) { c.persp.position.set(-span * 0.75, hmax * 2.4 + span * 0.25, span * 0.95); c.controls.target.set(0, hmax / 2, 0) }
    }
    c.framed = key
  }, [walls, products, sections, selected, mode, zones])

  return (
    <div className="viewer" ref={host} data-testid="viewer">
      <div className="hud">
        <button className={'b ' + (mode === '3d' ? '' : 'sec')} onClick={() => setMode('3d')}>3D</button>
        <button className={'b ' + (mode === 'elevation' ? '' : 'sec')} disabled={selected == null} onClick={() => setMode('elevation')}>Elevation</button>
        <button className="b sec" onClick={() => setZones(z => !z)}>{zones ? 'Hide' : 'Show'} wind end zones</button>
      </div>
      <div className="legend">
        <span><i className="sw" style={{ background: '#9fc7ad' }} />Checks pass</span><span><i className="sw" style={{ background: '#e19a94' }} />Check failing</span>
        <span><i className="sw" style={{ background: '#b9c4d2' }} />Not calculated / stale</span><span><i className="sw" style={{ background: '#c2410c' }} />Girts</span>
        <span><i className="sw" style={{ background: '#475569' }} />Columns</span><span><i className="sw" style={{ background: '#f59e0b' }} />End zone (after calc)</span>
        <span className="mut">Click a wall to select · drag to orbit</span>
      </div>
    </div>
  )
}
