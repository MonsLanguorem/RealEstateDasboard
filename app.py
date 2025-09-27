import React, { useMemo, useState, useEffect } from "react";
import { Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, AreaChart, Area, ReferenceArea } from "recharts";

// ================= Utilities =================
function mulberry32(a){return function(){a|=0;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^a>>>15,1|a);t=(t+Math.imul(t^t>>>7,61|t))^t;return((t^t>>>14)>>>0)/4294967296;}};
function rangeMonths(start,end){const res=[];const d=new Date(start.getFullYear(),start.getMonth(),1);while(d<=end){res.push(new Date(d));d.setMonth(d.getMonth()+1);}return res;}
// Formatting (always returns string)
function fmtMoney(v){const x=Number.isFinite(+v)?+v:0;return `A$ ${x.toLocaleString(undefined,{maximumFractionDigits:0})}`;}
function withAlpha(rgb,a){const m=rgb.match(/\d+/g)||[0,0,0];return `rgba(${m[0]},${m[1]},${m[2]},${a})`;}

// Green→Yellow→Red scale. If invert=true, low=red (e.g., income low плохо).
function colorGYR(value,min,max,invert=false){if(!Number.isFinite(value)) return "#ccc";const t=(value-min)/(max-min+1e-9);const u=Math.max(0,Math.min(1,t));const x=invert?1-u:u; // 0→green, 1→red
// piecewise: green(0,128,0) → yellow(255,215,0) → red(220,20,60)
let r,g,b;if(x<0.5){const k=x/0.5; r=Math.round(0+(255-0)*k); g=Math.round(128+(215-128)*k); b=Math.round(0+(0-0)*k);} else {const k=(x-0.5)/0.5; r=Math.round(255+(220-255)*k); g=Math.round(215+(20-215)*k); b=Math.round(0+(60-0)*k);} return `rgb(${r},${g},${b})`;}

// Format metric value for display
function fmtMetric(metric,val){if(!Number.isFinite(val)) return "—";switch(metric){case 'RTI': return (val*100).toFixed(1)+"%";case 'PTI': return val.toFixed(1);case 'Median Rent': return fmtMoney(Math.round(val))+"/нед";case 'Median Rent (month)': return fmtMoney(Math.round(val))+"/мес";case 'Median Price': return fmtMoney(Math.round(val));case 'Median Income': return fmtMoney(Math.round(val))+"/год";case 'Payment Cap Gap':{const p=(val*100).toFixed(1)+"%";return (val<=0?"✅ ":"❌ ")+p;}default:return String(val);}}

// Simple mortgage annuity
function annuityMonthly(L,rAnnual,years){
  const loan=Math.max(0,+L||0);
  const m=(+rAnnual||0)/12;
  const n=Math.max(1,(+years||0)*12);
  if(loan===0) return 0;
  if(m===0) return loan/n;
  return (m*loan)/(1-Math.pow(1+m,-n));
}
// Inverse: given monthly payment, get maximum principal one can borrow
function principalFromMonthly(payment,rAnnual,years){
  const m=(+rAnnual||0)/12;
  const n=Math.max(1,(+years||0)*12);
  if(m===0) return (+payment||0)*n;
  return (+payment||0) * (1 - Math.pow(1+m,-n)) / m;
}

// ================= Synthetic data =================
function useSyntheticData(){return useMemo(()=>{const rng=mulberry32(20250926);const sa2=Array.from({length:12},(_,i)=>({code:`SA2_${String(i+1).padStart(2,"0")}`}));const nCols=4;sa2.forEach((s,i)=>{s.r=Math.floor(i/nCols);s.c=i%nCols;});const months=rangeMonths(new Date(2015,0,1),new Date(2025,8,1));const rows=[];sa2.forEach((s)=>{let price=650000+rng()*950000;let rent=420+rng()*480;let income=70000+rng()*55000;const gp=0.0018+(rng()-0.5)*0.0008;const gr=0.0012+(rng()-0.5)*0.0006;const gi=0.0009+(rng()-0.5)*0.0005;months.forEach((dt,t)=>{const seas=1+0.02*Math.sin(2*Math.PI*(t%12)/12);price*=1+gp+Math.max(-0.003,Math.min(0.003,(rng()-0.5)*0.002));rent*=1+gr+Math.max(-0.002,Math.min(0.002,(rng()-0.5)*0.0016));income*=1+gi+Math.max(-0.0015,Math.min(0.0015,(rng()-0.5)*0.0012));const P=Math.max(250000,price*seas+(rng()-0.5)*24000);const Rw=Math.max(250,rent*seas+(rng()-0.5)*16);const I=Math.max(40000,income*(0.995+(rng()-0.5)*0.004));rows.push({date:dt.toISOString().slice(0,7),SA2_CODE:s.code,MedianPrice:P,MedianRent_week:Rw,MedianIncome_annual:I});});});return {sa2,months,rows};},[]);} 

const RENT_BEDROOM_COEFFS={1:1.00,2:1.35,3:1.75};
const PRICE_BEDROOM_COEFFS={1:0.85,2:1.00,3:1.25}; // оценочные, чтобы учесть размер при покупке

// ================= Component =================
export default function App(){
  const {sa2,months,rows}=useSyntheticData();
  const [segment,setSegment]=useState("buyers"); // "tenants" | "buyers"
  const [metric,setMetric]=useState("RTI");
  const [bedrooms,setBedrooms]=useState(2); // влияет на аренду и на цену (оценочно)
  const [preset,setPreset]=useState("5y");
  // Personal finances
  const [savings,setSavings]=useState(40000);
  const [incomeUser,setIncomeUser]=useState(95000);
  // Removed Saving Rate control to avoid confusion: focus on monthly cap
  const [depositPct,setDepositPct]=useState(20);
  const [interest,setInterest]=useState(6.0); // ипотечная ставка
  const [mortgageYears,setMortgageYears]=useState(25); // can change 1–30
  const fixedMortgageYears=25; // used for cap calculations on MAP for comparability
  const [selected,setSelected]=useState(sa2.slice(0,3).map(x=>x.code));
  const [focusSA2,setFocusSA2]=useState(sa2[0].code);
  const [useRealGeo,setUseRealGeo]=useState(true);
  const [geojson,setGeojson]=useState(null); // попытка загрузить реальные SA2
  const [geoStatus,setGeoStatus]=useState('idle'); // 'idle'|'loading'|'ready'|'error'

  // Keep only one key control: MAX MONTHLY MORTGAGE PAYMENT
  const [maxMonthly,setMaxMonthly]=useState(2500); // A$ cap for mortgage
  const [targetMTI,setTargetMTI]=useState(30); // for required-income calc

  // Hover tooltip state for map
  const [hover,setHover]=useState(null); // {x,y, code, val}

  useEffect(()=>{ 
    if(!useRealGeo){ setGeojson(null); setGeoStatus('idle'); return; }
    let aborted=false; setGeoStatus('loading');
    (async()=>{
      const urls=[
        'https://raw.githubusercontent.com/centreborelli/geo-aus/master/ABS/2016/SA2/sa2_2016_sydney_simplified.geojson',
        'https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/australia/sa2/sydney_sa2.json'
      ];
      for(const url of urls){
        try{
          const r=await fetch(url,{mode:'cors'});
          if(!r.ok) throw new Error('HTTP '+r.status);
          const gj=await r.json();
          if(!aborted && gj && gj.features && gj.features.length){ setGeojson(gj); setGeoStatus('ready'); return; }
        }catch(e){ /* continue */ }
      }
      if(!aborted){ setGeojson(null); setGeoStatus('error'); }
    })();
    return ()=>{aborted=true};
  },[useRealGeo]);

  // timeframe
  const endIndex=months.length-1;
  const lastMonthStr=months[endIndex].toISOString().slice(0,7);
  const startIndex=useMemo(()=>{if(preset==="Max") return 0; if(preset==="1y") return Math.max(0,endIndex-12); if(preset==="3y") return Math.max(0,endIndex-36); return Math.max(0,endIndex-60);},[preset,endIndex]);
  const monthSet=new Set(months.slice(startIndex).map(d=>d.toISOString().slice(0,7)));
  const filtered=rows.filter(r=>monthSet.has(r.date));

  // latest snapshot by SA2
  const bySA2Latest=useMemo(()=>{const arr=filtered.filter(r=>r.date===lastMonthStr); const brR=RENT_BEDROOM_COEFFS[bedrooms]||1; const brP=PRICE_BEDROOM_COEFFS[bedrooms]||1; return arr.map(r=>({...r, MedianRent_week_adj:r.MedianRent_week*brR, MedianPrice_adj:r.MedianPrice*brP, PTI:(r.MedianPrice*brP)/r.MedianIncome_annual, RTI:(r.MedianRent_week*brR*52)/r.MedianIncome_annual })); },[filtered,bedrooms,lastMonthStr]);

  const focusRow = bySA2Latest.find(x=>x.SA2_CODE===focusSA2) || bySA2Latest[0];

  // ---- Buyer calculations (size-adjusted price)
  const priceAdj = Number(focusRow?.MedianPrice_adj||0);
  const income = Number(incomeUser||0);
  const depositTarget = (Number(depositPct||0)/100)*priceAdj;
  const loanPrincipal = Math.max(0, priceAdj - depositTarget);
  const monthlyPayment = annuityMonthly(loanPrincipal, Number(interest||0)/100, Math.max(1, Number(mortgageYears||1)));
  const mti = (monthlyPayment*12) / Math.max(1e-9, income);

  // Payment-cap computations
  // Map baseline: fixed 25y for apples-to-apples coloring across SA2
  const LcapMap = principalFromMonthly(Number(maxMonthly||0), Number(interest||0)/100, fixedMortgageYears);
  // User card: use the user-selected mortgageYears
  const LcapUser = principalFromMonthly(Number(maxMonthly||0), Number(interest||0)/100, Math.max(1, Number(mortgageYears||1)));
  const capGapBySA2 = useMemo(()=>{
    return bySA2Latest.map(r=>{
      const P = r.MedianPrice_adj; const L_needed = P*(1 - (Number(depositPct||0)/100));
      const gap = (L_needed - LcapMap)/Math.max(1e-9,P); // ≤0 → affordable
      return { SA2_CODE:r.SA2_CODE, gap, P, L_needed };
    });
  },[bySA2Latest, depositPct, LcapMap]);

  // strings for JSX
  const S_priceAdj = useMemo(()=>fmtMoney(Math.round(priceAdj)),[priceAdj]);
  const S_depositTarget = useMemo(()=>fmtMoney(Math.round(depositTarget)),[depositTarget]);
  const S_income = useMemo(()=>fmtMoney(Math.round(income)),[income]);
  const rentAdjWeek = Number(focusRow?.MedianRent_week_adj||0);
  const rentAdjMonth = rentAdjWeek*52/12;
  const rtiUser = (rentAdjWeek*52)/Math.max(1e-9, income);
  const S_rentAdjWeek = useMemo(()=>fmtMoney(Math.round(rentAdjWeek)),[rentAdjWeek]);
  const S_rentAdjMonth = useMemo(()=>fmtMoney(Math.round(rentAdjMonth)),[rentAdjMonth]);

  // Map helpers
  function higherIsBad(metricName){return ["Median Price","Median Rent","PTI","RTI","Payment Cap Gap"].includes(metricName);} // Income — наоборот
  function valueForMetric(row){if(!row) return NaN; if(metric==="Median Rent") return row.MedianRent_week_adj; if(metric==="Median Price") return row.MedianPrice_adj; if(metric==="Median Income") return row.MedianIncome_annual; if(metric==="PTI") return row.PTI; if(metric==="Payment Cap Gap"){ const g = capGapBySA2.find(x=>x.SA2_CODE===row.SA2_CODE)?.gap; return g; } return row.RTI;}
  const metricValsRaw=bySA2Latest.map(valueForMetric).filter(v=>Number.isFinite(v)); const minV=metricValsRaw.length?Math.min(...metricValsRaw):0; const maxV=metricValsRaw.length?Math.max(...metricValsRaw):1;
  const focusVal = valueForMetric(focusRow||{});

  // Tooltip helpers
  function onCellEnter(e, code, val){try{const svg=e.currentTarget.ownerSVGElement; const rect=svg.getBoundingClientRect(); setHover({x:e.clientX-rect.left+8,y:e.clientY-rect.top+8,code,val});}catch(err){/* noop */}}
  function onCellMove(e){if(!hover) return; try{const svg=e.currentTarget.ownerSVGElement||e.currentTarget; const rect=svg.getBoundingClientRect(); setHover(h=>h?{...h,x:e.clientX-rect.left+8,y:e.clientY-rect.top+8}:h);}catch(err){}}
  function onCellLeave(){setHover(null);} 

  // ================= UI =================
  return (
    <div className="p-4 space-y-4">
      <h1 className="text-2xl font-semibold">🏠 Дэшборд доступности жилья — Sydney (SA2, синтетика)</h1>
      <p className="text-sm opacity-80">Выберите режим сверху. <b>Аренда</b> — ищем доступную аренду; <b>Покупка</b> — считаем бюджет и платежи. Зелёный цвет — лучше, красный — хуже.</p>

      {/* Global segment switch */}
      <div className="flex items-center gap-3 p-2 rounded-xl bg-white shadow w-max">
        <button className={`px-3 py-1 rounded-lg ${segment==='tenants'?'bg-gray-900 text-white':'bg-gray-100'}`} onClick={()=>setSegment('tenants')}>Аренда (tenants)</button>
        <button className={`px-3 py-1 rounded-lg ${segment==='buyers'?'bg-gray-900 text-white':'bg-gray-100'}`} onClick={()=>setSegment('buyers')}>Покупка (buyers)</button>
      </div>

      {/* Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="col-span-1 space-y-3 p-4 rounded-2xl shadow bg-white">
          <h2 className="font-medium">Карта: слой</h2>
          <select className="w-full border rounded p-2" value={metric} onChange={e=>setMetric(e.target.value)}>
            <option>RTI</option>
            <option>PTI</option>
            <option>Median Rent</option>
            <option>Median Price</option>
            <option>Median Income</option>
            <option>Payment Cap Gap</option>
          </select>
          <label className="text-sm">Спален: {bedrooms}</label>
          <input type="range" min={1} max={3} value={bedrooms} onChange={e=>setBedrooms(+e.target.value)} />
          <div className="flex items-center gap-2 mt-2">
            <input id="realgeo" type="checkbox" className="scale-110" checked={useRealGeo} onChange={e=>setUseRealGeo(e.target.checked)} />
            <label htmlFor="realgeo" className="text-sm">Реальные SA2 полигоны</label>
            {useRealGeo && (
              <span className="text-xs ml-2 px-2 py-0.5 rounded bg-gray-100">
                {geoStatus==='loading' && 'загрузка…'}
                {geoStatus==='ready' && 'готово'}
                {geoStatus==='error' && 'не удалось загрузить — используем сетку'}
              </span>
            )}
          </div>

          <hr className="my-2" />
          <h2 className="font-medium">Период</h2>
          <select className="w-full border rounded p-2" value={preset} onChange={e=>setPreset(e.target.value)}>
            <option value="Max">Max</option>
            <option value="5y">5 лет</option>
            <option value="3y">3 года</option>
            <option value="1y">1 год</option>
          </select>

          <hr className="my-2" />
          <h2 className="font-medium">Сравнение районов</h2>
          <div className="space-y-2 max-h-48 overflow-auto border rounded p-2">
            {sa2.map(s=> (
              <label key={s.code} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={selected.includes(s.code)} onChange={()=>{ if(selected.includes(s.code)) setSelected(selected.filter(x=>x!==s.code)); else if(selected.length<3) setSelected([...selected,s.code]); }} />
                {s.code}
              </label>
            ))}
          </div>
        </div>

        {/* Map */}
        <div className="col-span-3 p-4 rounded-2xl shadow bg-white">
          <h2 className="font-medium mb-2">🗺️ Карта SA2. {useRealGeo?"Реальный слой (если загрузился)":"Упрощённая сетка"}. Клик — выбрать район. Наведи мышкой — подсказка.</h2>
          {!useRealGeo || !geojson ? (
            // ---- Fallback SVG grid map
            <div className="relative">
              <svg viewBox="0 0 400 300" className="w-full h-[340px] rounded-xl border" onMouseMove={onCellMove}>
                {sa2.map((s)=>{const w=400/4; const h=300/3; const x=s.c*w; const y=s.r*h; const row=bySA2Latest.find(r=>r.SA2_CODE===s.code); const val=valueForMetric(row||{}); const color=colorGYR(val,minV,maxV, !higherIsBad(metric)); const focus=s.code===focusSA2; return (
                  <g key={s.code} onClick={()=>setFocusSA2(s.code)} onMouseEnter={(e)=>onCellEnter(e,s.code,fmtMetric(metric,val))} onMouseLeave={onCellLeave} style={{cursor:'pointer'}}>
                    <rect x={x+2} y={y+2} width={w-4} height={h-4} rx={8} fill={color} stroke={focus?"#111":"#fff"} strokeWidth={focus?3:2}/>
                    <text x={x+w/2} y={y+h/2} textAnchor="middle" dominantBaseline="middle" fontSize="12" fill="#000" style={{userSelect:'none'}}>{s.code}</text>
                    <title>{`${s.code} — ${metric}: ${fmtMetric(metric,val)}\nДата: ${lastMonthStr}`}</title>
                  </g>);} )}
              </svg>
              {hover && (
                <div className="absolute pointer-events-none bg-white/95 border rounded-lg shadow px-2 py-1 text-xs" style={{left:hover.x, top:hover.y}}>
                  <div><b>{hover.code}</b></div>
                  <div>{metric}: <b>{hover.val}</b></div>
                  <div>Дата: {lastMonthStr}</div>
                </div>
              )}
            </div>
          ) : (
            // ---- Render real GeoJSON polygons with simple projection + zoom/pan
            <>
              <GeoMapSA2
                geojson={geojson}
                metric={metric}
                bedrooms={bedrooms}
                depositPct={depositPct}
                interest={interest}
                maxMonthly={maxMonthly}
                lastMonthStr={lastMonthStr}
                onHover={setHover}
                onLeave={()=>setHover(null)}
                onFocus={setFocusSA2}
              />
              {hover && (
                <div className="relative">
                  <div className="absolute pointer-events-none bg-white/95 border rounded-lg shadow px-2 py-1 text-xs" style={{left:Math.max(0,hover.x), top:Math.max(0,hover.y)}}>
                    <div><b>{hover.code}</b></div>
                    <div>{metric}: <b>{hover.val}</b></div>
                    <div>Дата: {lastMonthStr}</div>
                  </div>
                </div>
              )}
            </>
          )}
          <div className="text-xs opacity-70 mt-1">Метрика: <b>{metric}</b>. Фокус: <b>{focusSA2}</b> — <b>{fmtMetric(metric, focusVal)}</b>. Цвета: зелёный — лучше/дешевле, красный — хуже/дороже.</div>
        </div>
      </div>

      {/* Comparison table */}
      <div className="p-4 rounded-2xl shadow bg-white">
        <h2 className="font-medium mb-2">📊 Сравнение выбранных SA2</h2>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50"><th className="p-2 text-left">SA2</th><th className="p-2 text-right">Median Price (adj)</th><th className="p-2 text-right">Median Rent ({bedrooms}BR, /нед)</th><th className="p-2 text-right">Median Income (/год)</th><th className="p-2 text-right">PTI</th><th className="p-2 text-right">RTI</th><th className="p-2 text-right">Payment Cap Gap</th></tr></thead>
            <tbody>
              {bySA2Latest.filter(r=>selected.includes(r.SA2_CODE)).map(r=> {const gap=capGapBySA2.find(x=>x.SA2_CODE===r.SA2_CODE)?.gap; return (
                <tr key={r.SA2_CODE} className="border-t">
                  <td className="p-2">{r.SA2_CODE}</td>
                  <td className="p-2 text-right">{fmtMoney(Math.round(r.MedianPrice_adj))}</td>
                  <td className="p-2 text-right">{fmtMoney(Math.round(r.MedianRent_week_adj))}</td>
                  <td className="p-2 text-right">{fmtMoney(Math.round(r.MedianIncome_annual))}</td>
                  <td className="p-2 text-right">{r.PTI.toFixed(1)}</td>
                  <td className="p-2 text-right">{(r.RTI*100).toFixed(1)}%</td>
                  <td className="p-2 text-right">{Number.isFinite(gap)? (gap<=0?"✅":"❌")+" "+(gap*100).toFixed(1)+"%": "—"}</td>
                </tr>
              );})}
            </tbody>
          </table>
        </div>
      </div>

      {/* Panels: show one based on segment */}
      {segment==='buyers' ? (
        <BuyerPanel {...{priceAdj, income, setIncomeUser, savings, setSavings, depositPct, setDepositPct, interest, setInterest, mortgageYears, setMortgageYears, S_priceAdj, S_depositTarget, S_income, LcapMap, LcapUser, maxMonthly, setMaxMonthly, targetMTI, setTargetMTI, mti}} />
      ) : (
        <TenantPanel {...{focusSA2, bedrooms, rentAdjWeek, rentAdjMonth, rtiUser, S_rentAdjWeek, S_rentAdjMonth, incomeUser, setIncomeUser}} />
      )}

      {/* Time series with informative coloring and thick city median */}
      <div className="p-4 rounded-2xl shadow bg-white">
        <h2 className="font-medium mb-2">📈 Динамика</h2>
        {segment==='tenants' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ChartBlock title={`Median Rent (${bedrooms}BR, месяц)`} seriesKey="RentMonthly" ts={tsWithMedian(rows, months, startIndex, bedrooms, selected, sa2)} colorizer={(v,min,max)=>colorGYR(v,min,max,true)} />
            <ChartBlock title="RTI (аренда/доход)" seriesKey="RTI" ts={tsWithMedian(rows, months, startIndex, bedrooms, selected, sa2)} thresholds={{green:[0,0.25], amber:[0.25,0.30], red:[0.30,1.0]}} colorizer={(v,min,max)=>colorGYR(v,min,max,true)} />
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ChartBlock title={`Median Rent (${bedrooms}BR, неделя)`} seriesKey="Rent" ts={tsWithMedian(rows, months, startIndex, bedrooms, selected, sa2)} colorizer={(v,min,max)=>colorGYR(v,min,max,true)} />
            <ChartBlock title="Median Price" seriesKey="Price" ts={tsWithMedian(rows, months, startIndex, bedrooms, selected, sa2)} colorizer={(v,min,max)=>colorGYR(v,min,max,true)} />
            <ChartBlock title="PTI (цена/доход)" seriesKey="PTI" ts={tsWithMedian(rows, months, startIndex, bedrooms, selected, sa2)} thresholds={{green:[0,8], amber:[8,10], red:[10,99]}} colorizer={(v,min,max)=>colorGYR(v,min,max,true)} />
            <ChartBlock title="RTI (аренда/доход)" seriesKey="RTI" ts={tsWithMedian(rows, months, startIndex, bedrooms, selected, sa2)} thresholds={{green:[0,0.25], amber:[0.25,0.30], red:[0.30,1.0]}} colorizer={(v,min,max)=>colorGYR(v,min,max,true)} />
          </div>
        )}
      </div>

      {/* Explanations for humans */}
      <details className="p-4 rounded-2xl shadow bg-white">
        <summary className="cursor-pointer font-medium">ℹ️ Простые объяснения</summary>
        <div className="text-sm mt-2 space-y-2">
          <p><b>Макс. платёж в месяц</b> — сколько вы готовы отдавать банку каждый месяц. Мы сравниваем это с ценами районов и подсвечиваем, где покупка вписывается в бюджет.</p>
          <p><b>Median Rent</b> — средняя цена аренды в районе. Для 1/2/3 спален мы корректируем цену.</p>
          <p><b>RTI</b> — доля дохода, которая уйдёт на аренду за год. ≥30% — стресс.</p>
          <p><b>PTI</b> — цена жилья в годах дохода. Больше — сложнее купить.</p>
          <p><b>MTI</b> — доля дохода, которая будет уходить на ипотеку за год (зависит от ставки, срока и цены).</p>
          <p><b>Payment Cap Gap</b> — хватает ли кредита при вашем месячном лимите и текущем депозите. «✅ ≤ 0» — хватает.</p>
        </div>
      </details>

      <div className="text-xs opacity-70">⚠️ Данные синтетические. Коэффициенты по размеру жилья для цены — оценочные (1BR×0.85; 2BR×1.00; 3BR×1.25) и нужны лишь для примера. Для реального проекта подключим официальные источники ABS/NSW.</div>

</div>
  );
}

function BuyerPanel(props){
  const {priceAdj, income, setIncomeUser, savings, setSavings, depositPct, setDepositPct, interest, setInterest, mortgageYears, setMortgageYears, S_priceAdj, S_depositTarget, S_income, LcapMap, LcapUser, maxMonthly, setMaxMonthly, targetMTI, setTargetMTI, mti} = props;

  // Derived basics
  const depositTarget = (Number(depositPct||0)/100)*Number(priceAdj||0);
  const loanPrincipal = Math.max(0, Number(priceAdj||0) - depositTarget);
  const monthlyPayment = annuityMonthly(loanPrincipal, Number(interest||0)/100, Math.max(1, Number(mortgageYears||1)));
  const monthly25 = annuityMonthly(loanPrincipal, Number(interest||0)/100, 25);
  const mti25 = (monthly25*12) / Math.max(1e-9, Number(income||0));

  // Modes inside BuyerPanel
  const [buyerMode,setBuyerMode]=useState('budget'); // 'budget' | 'fixed25' | 'termIncome'

  // Cards derived by mode
  const P_affordable = Number(LcapUser||0) / Math.max(1e-9, 1 - (Number(depositPct||0)/100)); // budget mode
  const incomeRequiredFixedSR = (monthlyPayment*12) / 0.25; // MTI fixed 25% for termIncome mode

  return (
    <div className="p-4 rounded-2xl shadow bg-white">
      <h2 className="font-medium mb-2">🏡 Покупка — понятные шаги</h2>

      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm mr-2">Режим:</span>
        <button className={`px-3 py-1 rounded-lg text-sm ${buyerMode==='budget'?'bg-gray-900 text-white':'bg-gray-100'}`} onClick={()=>setBuyerMode('budget')}>По бюджету (макс платёж)</button>
        <button className={`px-3 py-1 rounded-lg text-sm ${buyerMode==='fixed25'?'bg-gray-900 text-white':'bg-gray-100'}`} onClick={()=>setBuyerMode('fixed25')}>Фикс. 25 лет → ваш MTI</button>
        <button className={`px-3 py-1 rounded-lg text-sm ${buyerMode==='termIncome'?'bg-gray-900 text-white':'bg-gray-100'}`} onClick={()=>setBuyerMode('termIncome')}>Срок n → нужен доход (25%)</button>
      </div>

      <p className="text-sm mb-3 text-gray-700">Заполните простые поля. Мы покажем: <b>сколько стоит район</b>, <b>какой платёж будет по ипотеке</b>, <b>какой доход нужен</b> и <b>какие районы укладываются в ваш месячный бюджет</b>.</p>

      {/* Core personal inputs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm mb-3">
        <label className="p-3 rounded-xl bg-gray-50 flex flex-col">Ваш доход /год (A$)
          <input className="border rounded p-2 mt-1" type="number" value={Number.isFinite(income)?income:''} onChange={e=>setIncomeUser(+e.target.value||0)} placeholder="например, 95000" />
        </label>
        <label className="p-3 rounded-xl bg-gray-50 flex flex-col">Ваши накопления (A$)
          <input className="border rounded p-2 mt-1" type="number" value={Number.isFinite(savings)?savings:''} onChange={e=>setSavings(+e.target.value||0)} placeholder="например, 40000" />
          <span className="text-xs opacity-70 mt-1">Накопления идут на <b>депозит</b>.</span>
        </label>
        {buyerMode==='budget' && (
          <label className="p-3 rounded-xl bg-gray-50 flex flex-col">Макс. платёж по ипотеке (/мес)
            <input className="border rounded p-2 mt-1" type="number" value={Number.isFinite(maxMonthly)?maxMonthly:''} onChange={e=>setMaxMonthly(+e.target.value||0)} placeholder="например, 2500" />
            <span className="text-xs opacity-70 mt-1">Это ваш <b>комфортный месячный бюджет</b> на ипотеку.</span>
          </label>
        )}
      </div>

      {/* Financing controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm mb-3">
        <label className="p-3 rounded-xl bg-gray-50 flex flex-col">Deposit (%)
          <input type="range" min={5} max={30} value={depositPct} onChange={e=>setDepositPct(+e.target.value)} />
          <div className="mt-1">{depositPct}%</div>
        </label>
        <label className="p-3 rounded-xl bg-gray-50 flex flex-col">Ставка ипотеки (% годовых)
          <input type="range" min={2} max={10} step={0.1} value={interest} onChange={e=>setInterest(+e.target.value)} />
          <div className="mt-1">{Number(interest).toFixed(1)}%</div>
        </label>
        {buyerMode!=='fixed25' ? (
          <label className="p-3 rounded-xl bg-gray-50 flex flex-col">Срок ипотеки (лет)
            <input type="range" min={1} max={30} value={mortgageYears} onChange={e=>setMortgageYears(+e.target.value)} />
            <div className="mt-1">{mortgageYears} лет</div>
          </label>
        ) : (
          <div className="p-3 rounded-xl bg-gray-50 text-sm">Срок фиксирован: <b>25 лет</b></div>
        )}
      </div>

      {/* Mode-specific outputs */}
      {buyerMode==='budget' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">Доступная цена при вашем лимите</div>
            <div className="font-semibold">{fmtMoney(Math.round(P_affordable))}</div>
            <div className="text-xs opacity-70">Слой «Payment Cap Gap» на карте показывает районы, где это реально (✅).</div>
          </div>
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">Платёж при {mortgageYears} лет</div>
            <div className="font-semibold">{fmtMoney(Math.round(monthlyPayment))}/мес</div>
          </div>
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">MTI (доля дохода)</div>
            <div className="font-semibold">{(mti*100).toFixed(1)}%</div>
          </div>
        </div>
      )}

      {buyerMode==='fixed25' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">Платёж при 25 лет</div>
            <div className="font-semibold">{fmtMoney(Math.round(monthly25))}/мес</div>
          </div>
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">Ваша доля дохода на ипотеку (MTI)</div>
            <div className="font-semibold">{(mti25*100).toFixed(1)}%</div>
            <div className="text-xs opacity-70">До 30% — комфортно, 30–40% — повышенная нагрузка, >40% — тяжело.</div>
          </div>
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">Цена (учтён размер)</div>
            <div className="font-semibold">{S_priceAdj}</div>
          </div>
        </div>
      )}

      {buyerMode==='termIncome' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">Необходимый доход при MTI=25%</div>
            <div className="font-semibold">{fmtMoney(Math.round(incomeRequiredFixedSR))}</div>
            <div className="text-xs opacity-70">Мы фиксируем долю платежа от дохода на уровне 25% и рассчитываем, какой годовой доход нужен.</div>
          </div>
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">Платёж при {mortgageYears} лет</div>
            <div className="font-semibold">{fmtMoney(Math.round(monthlyPayment))}/мес</div>
          </div>
          <div className="p-3 rounded-xl bg-gray-50">
            <div className="opacity-60">Цена (учтён размер)</div>
            <div className="font-semibold">{S_priceAdj}</div>
          </div>
        </div>
      )}

      {/* Base facts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          <div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Цена (учтён размер)</div><div className="font-semibold">{S_priceAdj}</div></div>
          <div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Депозит (мин.)</div><div className="font-semibold">{S_depositTarget}</div></div>
          <div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Ваш доход /год</div><div className="font-semibold">{S_income}</div></div>
          <div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Платёж при {buyerMode==='fixed25'?25:mortgageYears} лет</div><div className="font-semibold">{fmtMoney(Math.round(buyerMode==='fixed25'?monthly25:monthlyPayment))}/мес</div></div>
          <div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">MTI (доля дохода)</div><div className="font-semibold">{( (buyerMode==='fixed25'?mti25:mti)*100 ).toFixed(1)}%</div></div>
        </div>
        <div className="p-3 rounded-xl bg-gray-50 text-sm">
          <div className="font-medium mb-1">👉 Пояснение простыми словами</div>
          <div>
            {buyerMode==='budget' && (<>«Макс. платёж /мес» — сколько вам удобно платить банку. Мы считаем, какой кредит можно взять и где покупка вписывается в бюджет (слой на карте).</>)}
            {buyerMode==='fixed25' && (<>Фиксируем срок 25 лет и показываем, <b>какую долю дохода</b> съест ипотека. Это помогает понять нагрузку без выбора срока.</>)}
            {buyerMode==='termIncome' && (<>Фиксируем долю платежа <b>25%</b> и по выбранному сроку считаем, <b>какой доход</b> нужен, чтобы спокойно тянуть ипотеку.</>)}
          </div>
        </div>
      </div>

      {(buyerMode!=='termIncome' && (mti>=0.40)) && <div className="mt-1 text-red-600 text-sm">⚠️ MTI ≥ 40% — высокая ипотечная нагрузка.</div>}
      {(buyerMode!=='termIncome' && (mti>=0.30 && mti<0.40)) && <div className="mt-1 text-amber-600 text-sm">⚠️ MTI 30–40% — повышенная нагрузка.</div>}
    </div>
  );
}

function TenantPanel({focusSA2, bedrooms, rentAdjWeek, rentAdjMonth, rtiUser, S_rentAdjWeek, S_rentAdjMonth, incomeUser, setIncomeUser}){
  return (
    <div className="p-4 rounded-2xl shadow bg-white">
      <h2 className="font-medium mb-2">🏘️ Аренда — {focusSA2}</h2>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm mb-3">
        <label className="p-3 rounded-xl bg-gray-50 flex flex-col">Ваш доход /год (A$)
          <input className="border rounded p-2 mt-1" type="number" value={incomeUser} onChange={e=>setIncomeUser(+e.target.value||0)} placeholder="например, 45000" />
        </label>
        <div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Аренда ({bedrooms}BR, неделя)</div><div className="font-semibold">{S_rentAdjWeek}</div></div>
        <div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Аренда ({bedrooms}BR, месяц)</div><div className="font-semibold">{S_rentAdjMonth}</div></div>
        <div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">RTI</div><div className="font-semibold">{(rtiUser*100).toFixed(1)}%</div></div>
      </div>
      {rtiUser>=0.30 && <div className="mt-2 text-red-600 text-sm">⚠️ RTI ≥ 30% — арендный стресс.</div>}
      {rtiUser>=0.25 && rtiUser<0.30 && <div className="mt-2 text-amber-600 text-sm">⚠️ RTI 25–30% — пограничная нагрузка.</div>}
      <div className="text-xs opacity-70 mt-2">RTI = (аренда за год / доход). Месячная аренда = недельная × 52 ÷ 12. Коэф. комнатности (аренда): 1.00/1.35/1.75.</div>
    </div>
  );
}

// ===== Real SA2 GeoJSON Map with zoom/pan =====
function GeoMapSA2({geojson, metric, bedrooms, depositPct, interest, maxMonthly, lastMonthStr, onHover, onLeave, onFocus}){
  function hash32(str){let h=2166136261>>>0; for(let i=0;i<str.length;i++){h^=str.charCodeAt(i); h=Math.imul(h,16777619);} return h>>>0;}
  function getName(p){return p?.SA2_NAME21||p?.SA2_NAME_2021||p?.SA2_NAME16||p?.SA2_NAME_2016||p?.SA2_NAME||p?.NAME||p?.id||'SA2';}
  function getCode(p){return p?.SA2_MAIN21||p?.SA2_MAINCODE_2021||p?.SA2_MAIN16||p?.SA2_MAINCODE_2016||p?.SA2_CODE||getName(p);}  
  function higherIsBadLocal(m){return ["Median Price","Median Rent","PTI","RTI","Payment Cap Gap"].includes(m);}  

  // Build bbox
  const coordsAll=[];
  geojson.features.forEach(f=>{
    const g=f.geometry; if(!g) return;
    const pushCoord=(c)=>{coordsAll.push(c)};
    const walk=(geom)=>{
      const type=geom.type; const cs=geom.coordinates;
      if(type==='Polygon') cs.forEach(r=>r.forEach(pt=>pushCoord(pt)));
      else if(type==='MultiPolygon') cs.forEach(poly=>poly.forEach(r=>r.forEach(pt=>pushCoord(pt))));
    };
    walk(g);
  });
  if(!coordsAll.length){return <div className="p-3 rounded-xl bg-gray-50">GeoJSON пуст.</div>;}

  const lons=coordsAll.map(c=>c[0]); const lats=coordsAll.map(c=>c[1]);
  const minLon=Math.min(...lons), maxLon=Math.max(...lons), minLat=Math.min(...lats), maxLat=Math.max(...lats);
  const W=800, H=520, pad=10;
  const sx=(W-2*pad)/(maxLon-minLon), sy=(H-2*pad)/(maxLat-minLat);
  const s=Math.min(sx,sy);
  const proj=([lon,lat])=>[ pad+(lon-minLon)*s, pad+(maxLat-lat)*s ];
  const pathFromGeom=(geom)=>{
    const cs=geom.coordinates; let d="";
    if(geom.type==='Polygon'){
      cs.forEach(r=>{r.forEach((pt,i)=>{const [x,y]=proj(pt); d+=(i?`L${x},${y}`:`M${x},${y}`)}); d+="Z";});
    } else if(geom.type==='MultiPolygon'){
      cs.forEach(poly=>{poly.forEach(r=>{r.forEach((pt,i)=>{const [x,y]=proj(pt); d+=(i?`L${x},${y}`:`M${x},${y}`)}); d+="Z";});});
    }
    return d;
  }

  // Synthetic values per feature (stable via hash)
  const LcapMap = principalFromMonthly(Number(maxMonthly||0), Number(interest||0)/100, 25);
  const RENT = {1:1.00,2:1.35,3:1.75}[bedrooms]||1;
  const vals = geojson.features.map(f=>{
    const p=f.properties||{}; const code=String(getCode(p)); const name=getName(p);
    // deterministic RNG seeded by SA2 code
    let seed=hash32(code); const rnd=()=>{seed|=0; seed=(seed+0x6D2B79F5)|0; let t=Math.imul(seed^seed>>>15,1|seed); t=(t+Math.imul(t^t>>>7,61|t))^t; return ((t^t>>>14)>>>0)/4294967296;};
    const price=600000 + rnd()*900000; const rentW=380 + rnd()*520; const income=65000 + rnd()*60000;
    const P = price * ({1:0.85,2:1.00,3:1.25}[bedrooms]||1);
    const Rw = rentW * RENT; const I = income;
    const PTI = P / I; const RTI = (Rw*52)/I;
    const L_needed = P*(1 - (Number(depositPct||0)/100));
    const gap = (L_needed - LcapMap)/Math.max(1e-9,P);
    const pick = metric==='Median Price'?P: metric==='Median Rent'?Rw: metric==='Median Income'?I: metric==='PTI'?PTI: metric==='Payment Cap Gap'?gap: RTI;
    return {name, code, value: pick, display: fmtMetric(metric, pick), geom:f.geometry};
  });
  const nums=vals.map(v=>v.value).filter(Number.isFinite);
  const vmin=Math.min(...nums), vmax=Math.max(...nums);

  // zoom/pan state
  const [scale,setScale]=React.useState(1);
  const [pan,setPan]=React.useState({x:0,y:0});
  const [drag,setDrag]=React.useState(null);
  const onWheel=(e)=>{e.preventDefault(); const k=Math.exp(-e.deltaY*0.001); setScale(s=>Math.max(0.8,Math.min(8,s*k)));};
  const onMouseDown=(e)=>setDrag({x:e.clientX,y:e.clientY,pan0:{...pan}});
  const onMouseMove=(e)=>{ if(!drag) return; setPan({x:drag.pan0.x+(e.clientX-drag.x), y:drag.pan0.y+(e.clientY-drag.y)}); };
  const endDrag=()=>setDrag(null);

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[520px] rounded-xl border bg-white" onWheel={onWheel} onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={endDrag} onMouseLeave={()=>{endDrag(); onLeave&&onLeave();}}>
        <g transform={`translate(${pan.x} ${pan.y}) scale(${scale})`}>
          {vals.map(v=>{const d=pathFromGeom(v.geom); const color=colorGYR(v.value, vmin, vmax, !higherIsBadLocal(metric)); return (
            <path key={v.code} d={d} fill={color} stroke="#fff" strokeWidth={0.8} onMouseEnter={(e)=>{const rect=e.currentTarget.ownerSVGElement.getBoundingClientRect(); onHover&&onHover({x:e.clientX-rect.left+8,y:e.clientY-rect.top+8,code:v.name,val:v.display});}} onMouseLeave={()=>onLeave&&onLeave()} onClick={()=>onFocus&&onFocus(v.name)}>
              <title>{`${v.name} — ${metric}: ${v.display}
Дата: ${lastMonthStr}`}</title>
            </path>
          );})}
        </g>
      </svg>
      <div className="absolute top-2 right-2 bg-white/90 rounded-md shadow px-2 py-1 text-xs">Зум: колесо • Пан: перетаскивание</div>
    </div>
  );
}

// ============= Helpers for charts (with city median) =============
function tsWithMedian(rows, months, startIndex, bedrooms, selected, sa2){
  const RENT = RENT_BEDROOM_COEFFS[bedrooms] || 1;
  const set = new Set(months.slice(startIndex).map(d => d.toISOString().slice(0,7)));

  // Build per-code series only for selected codes (fallback to first SA2)
  const seriesByCode = {};
  (selected.length ? selected : [sa2[0].code]).forEach(code => seriesByCode[code] = []);
  rows.forEach(r => {
    if (!set.has(r.date)) return;
    if (seriesByCode[r.SA2_CODE]) {
      seriesByCode[r.SA2_CODE].push({
        date: r.date,
        Rent: r.MedianRent_week * RENT,
        RentMonthly: r.MedianRent_week * RENT * 52/12,
        Price: r.MedianPrice,
        PTI: r.MedianPrice / r.MedianIncome_annual,
        RTI: (r.MedianRent_week * RENT * 52) / r.MedianIncome_annual
      });
    }
  });

  // City-wide median per date across all SA2
  const grouped = new Map();
  rows.forEach(r => {
    if (!set.has(r.date)) return;
    if (!grouped.has(r.date)) grouped.set(r.date, []);
    grouped.get(r.date).push({
      Rent: r.MedianRent_week * RENT,
      RentMonthly: r.MedianRent_week * RENT * 52/12,
      Price: r.MedianPrice,
      PTI: r.MedianPrice / r.MedianIncome_annual,
      RTI: (r.MedianRent_week * RENT * 52) / r.MedianIncome_annual
    });
  });
  const medianSeries = Array.from(grouped.keys()).sort().map(d => {
    const arr = grouped.get(d);
    function med(key){
      const xs = arr.map(a => a[key]).sort((a,b) => a-b);
      const k = Math.floor(xs.length/2);
      return xs.length % 2 ? xs[k] : (xs[k-1] + xs[k]) / 2;
    }
    return { date: d, value: { Rent: med('Rent'), RentMonthly: med('RentMonthly'), Price: med('Price'), PTI: med('PTI'), RTI: med('RTI') } };
  });

  return { seriesByCode, medianSeries };
}

function ChartBlock({title,seriesKey,ts,thresholds,colorizer}){
  const codes = Object.keys(ts.seriesByCode);
  // Collect values for domain calc
  const allVals = codes
    .flatMap(c => (ts.seriesByCode[c] || []).map(p => p[seriesKey]))
    .concat(ts.medianSeries.map(p => p.value[seriesKey]))
    .filter(v => Number.isFinite(v));

  const vmin = allVals.length ? Math.min(...allVals) : 0;
  const vmax = allVals.length ? Math.max(...allVals) : 1;
  const pad = (vmax - vmin) * 0.08 || 1;
  const domain = [vmin - pad, vmax + pad];

  // Собираем данные по датам: базируемся на городском медианном ряду
  const perCodeMap = {};
  codes.forEach(c => {
    perCodeMap[c] = new Map((ts.seriesByCode[c] || []).map(p => [p.date, p[seriesKey]]));
  });

  const data = ts.medianSeries.map(m => {
    const row = { date: m.date, median: m.value[seriesKey] };
    codes.forEach(c => { row[c] = perCodeMap[c].get(m.date); });
    return row;
  });

  function colorForSeries(code){
    const arr = ts.seriesByCode[code] || [];
    const last = arr.length ? arr[arr.length - 1][seriesKey] : NaN;
    try{
      return colorizer ? colorizer(last, vmin, vmax) : '#3b82f6';
    }catch(_){
      return '#3b82f6';
    }
  }

  function fmtForKey(v){
    switch (seriesKey){
      case 'RentMonthly': return fmtMetric('Median Rent (month)', v);
      case 'Rent':        return fmtMetric('Median Rent', v);
      case 'Price':       return fmtMetric('Median Price', v);
      case 'PTI':         return fmtMetric('PTI', v);
      case 'RTI':         return fmtMetric('RTI', v);
      default:            return String(v);
    }
  }

  return (
    <div className="p-3 rounded-xl bg-gray-50">
      <div className="font-medium mb-2">{title}</div>
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ left: 8, right: 8, top: 10, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis domain={domain} tick={{ fontSize: 12 }} />

          {/* Пороговые зоны (если заданы) */}
          {thresholds?.green && Number.isFinite(thresholds.green[0]) && Number.isFinite(thresholds.green[1]) && (
            <ReferenceArea y1={thresholds.green[0]} y2={thresholds.green[1]} fill="rgba(0,128,0,0.08)" strokeOpacity={0} />
          )}
          {thresholds?.amber && Number.isFinite(thresholds.amber[0]) && Number.isFinite(thresholds.amber[1]) && (
            <ReferenceArea y1={thresholds.amber[0]} y2={thresholds.amber[1]} fill="rgba(255,215,0,0.10)" strokeOpacity={0} />
          )}
          {thresholds?.red && Number.isFinite(thresholds.red[0]) && Number.isFinite(thresholds.red[1]) && (
            <ReferenceArea y1={thresholds.red[0]} y2={thresholds.red[1]} fill="rgba(220,20,60,0.08)" strokeOpacity={0} />
          )}

          <Tooltip
            formatter={(val, name) => [fmtForKey(val), name === 'median' ? 'City median' : String(name)]}
            labelFormatter={(label) => `Месяц: ${label}`}
          />

          {/* Линии по выбранным SA2 */}
          {codes.map(code => (
            <Line
              key={code}
              type="monotone"
              dataKey={code}
              dot={false}
              stroke={colorForSeries(code)}
              strokeWidth={2}
              name={code}
            />
          ))}

          {/* Жирная линия медианы города */}
          <Line
            type="monotone"
            dataKey="median"
            dot={false}
            stroke="#111"
            strokeWidth={3}
            name="City median"
          />

          <Legend />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
