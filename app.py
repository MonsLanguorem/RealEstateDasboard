import streamlit as st
import streamlit.components.v1 as components

components.html("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <script src="https://cdn.tailwindcss.com"></script>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/recharts/umd/Recharts.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone@7/babel.min.js"></script>
  <style>html,body,#root{height:100%;background:#f5f5f5;margin:0}</style>
</head>
<body>
<div id="root"></div>

<script type="text/babel" data-presets="env,react">
const {useMemo,useState,useEffect}=React;
const {Line,XAxis,YAxis,Tooltip,Legend,ResponsiveContainer,CartesianGrid,AreaChart,Area,ReferenceArea}=Recharts;

function mulberry32(a){return function(){a|=0;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^a>>>15,1|a);t=(t+Math.imul(t^t>>>7,61|t))^t;return((t^t>>>14)>>>0)/4294967296;}}
function rangeMonths(s,e){const r=[],d=new Date(s.getFullYear(),s.getMonth(),1);while(d<=e){r.push(new Date(d));d.setMonth(d.getMonth()+1)}return r}
function fmtMoney(v){const x=Number.isFinite(+v)?+v:0;return`A$ ${x.toLocaleString(undefined,{maximumFractionDigits:0})}`}
function withAlpha(rgb,a){const m=rgb.match(/\\d+/g)||[0,0,0];return`rgba(${m[0]},${m[1]},${m[2]},${a})`}
function colorGYR(v,min,max,invert=false){if(!Number.isFinite(v))return"#ccc";const t=(v-min)/(max-min+1e-9),u=Math.max(0,Math.min(1,t));const x=invert?1-u:u;let r,g,b;if(x<.5){const k=x/.5;r=Math.round(0+(255-0)*k);g=Math.round(128+(215-128)*k);b=Math.round(0)}else{const k=(x-.5)/.5;r=Math.round(255+(220-255)*k);g=Math.round(215+(20-215)*k);b=Math.round(0+(60-0)*k)}return`rgb(${r},${g},${b})`}
function fmtMetric(m,v){if(!Number.isFinite(v))return"—";switch(m){case"RTI":return(v*100).toFixed(1)+"%";case"PTI":return v.toFixed(1);case"Median Rent":return fmtMoney(Math.round(v))+"/нед";case"Median Rent (month)":return fmtMoney(Math.round(v))+"/мес";case"Median Price":return fmtMoney(Math.round(v));case"Median Income":return fmtMoney(Math.round(v))+"/год";case"Payment Cap Gap":{const p=(v*100).toFixed(1)+"%";return(v<=0?"✅ ":"❌ ")+p}default:return String(v)}}
function annuityMonthly(L,ra,y){const loan=Math.max(0,+L||0);const m=(+ra||0)/12;const n=Math.max(1,(+y||0)*12);if(loan===0)return 0;if(m===0)return loan/n;return(m*loan)/(1-Math.pow(1+m,-n))}
function principalFromMonthly(p,ra,y){const m=(+ra||0)/12;const n=Math.max(1,(+y||0)*12);if(m===0)return(+p||0)*n;return(+p||0)*(1-Math.pow(1+m,-n))/m}

function useSyntheticData(){return useMemo(()=>{const rng=mulberry32(20250926);const sa2=Array.from({length:12},(_,i)=>({code:`SA2_${String(i+1).padStart(2,"0")}`}));const nCols=4;sa2.forEach((s,i)=>{s.r=Math.floor(i/nCols);s.c=i%nCols});const months=rangeMonths(new Date(2015,0,1),new Date(2025,8,1));const rows=[];sa2.forEach(s=>{let price=650000+rng()*950000;let rent=420+rng()*480;let income=70000+rng()*55000;const gp=.0018+(rng()-.5)*.0008,gr=.0012+(rng()-.5)*.0006,gi=.0009+(rng()-.5)*.0005;months.forEach((dt,t)=>{const seas=1+.02*Math.sin(2*Math.PI*(t%12)/12);price*=1+gp+Math.max(-.003,Math.min(.003,(rng()-.5)*.002));rent*=1+gr+Math.max(-.002,Math.min(.002,(rng()-.5)*.0016));income*=1+gi+Math.max(-.0015,Math.min(.0015,(rng()-.5)*.0012));const P=Math.max(250000,price*seas+(rng()-.5)*24000);const Rw=Math.max(250,rent*seas+(rng()-.5)*16);const I=Math.max(40000,income*(.995+(rng()-.5)*.004));rows.push({date:dt.toISOString().slice(0,7),SA2_CODE:s.code,MedianPrice:P,MedianRent_week:Rw,MedianIncome_annual:I})})});return{sa2,months,rows}},[])}
const RENT_BEDROOM_COEFFS={1:1.00,2:1.35,3:1.75};
const PRICE_BEDROOM_COEFFS={1:.85,2:1.00,3:1.25};

function App(){
  const{sa2,months,rows}=useSyntheticData();
  const[segment,setSegment]=useState("buyers");
  const[metric,setMetric]=useState("RTI");
  const[bedrooms,setBedrooms]=useState(2);
  const[preset,setPreset]=useState("5y");
  const[savings,setSavings]=useState(40000);
  const[incomeUser,setIncomeUser]=useState(95000);
  const[depositPct,setDepositPct]=useState(20);
  const[interest,setInterest]=useState(6.0);
  const[mortgageYears,setMortgageYears]=useState(25);
  const fixedMortgageYears=25;
  const[selected,setSelected]=useState(sa2.slice(0,3).map(x=>x.code));
  const[focusSA2,setFocusSA2]=useState(sa2[0].code);
  const[useRealGeo,setUseRealGeo]=useState(true);
  const[geojson,setGeojson]=useState(null);
  const[geoStatus,setGeoStatus]=useState('idle');
  const[maxMonthly,setMaxMonthly]=useState(2500);
  const[targetMTI,setTargetMTI]=useState(30);
  const[hover,setHover]=useState(null);

  useEffect(()=>{if(!useRealGeo){setGeojson(null);setGeoStatus('idle');return}let aborted=false;setGeoStatus('loading');(async()=>{const urls=['https://raw.githubusercontent.com/centreborelli/geo-aus/master/ABS/2016/SA2/sa2_2016_sydney_simplified.geojson','https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/australia/sa2/sydney_sa2.json'];for(const url of urls){try{const r=await fetch(url,{mode:'cors'});if(!r.ok)throw new Error('HTTP '+r.status);const gj=await r.json();if(!aborted&&gj&&gj.features&&gj.features.length){setGeojson(gj);setGeoStatus('ready');return}}catch(e){}}if(!aborted){setGeojson(null);setGeoStatus('error')}})();return()=>{aborted=true}},[useRealGeo]);

  const endIndex=months.length-1;
  const lastMonthStr=months[endIndex].toISOString().slice(0,7);
  const startIndex=useMemo(()=>{if(preset==="Max")return 0;if(preset==="1y")return Math.max(0,endIndex-12);if(preset==="3y")return Math.max(0,endIndex-36);return Math.max(0,endIndex-60)},[preset,endIndex]);
  const monthSet=new Set(months.slice(startIndex).map(d=>d.toISOString().slice(0,7)));
  const filtered=rows.filter(r=>monthSet.has(r.date));

  const bySA2Latest=useMemo(()=>{const arr=filtered.filter(r=>r.date===lastMonthStr);const brR=RENT_BEDROOM_COEFFS[bedrooms]||1;const brP=PRICE_BEDROOM_COEFFS[bedrooms]||1;return arr.map(r=>({...r,MedianRent_week_adj:r.MedianRent_week*brR,MedianPrice_adj:r.MedianPrice*brP,PTI:(r.MedianPrice*brP)/r.MedianIncome_annual,RTI:(r.MedianRent_week*brR*52)/r.MedianIncome_annual}))},[filtered,bedrooms,lastMonthStr]);

  const focusRow=bySA2Latest.find(x=>x.SA2_CODE===focusSA2)||bySA2Latest[0];
  const priceAdj=Number(focusRow?.MedianPrice_adj||0);
  const income=Number(incomeUser||0);
  const depositTarget=(Number(depositPct||0)/100)*priceAdj;
  const loanPrincipal=Math.max(0,priceAdj-depositTarget);
  const monthlyPayment=annuityMonthly(loanPrincipal,Number(interest||0)/100,Math.max(1,Number(mortgageYears||1)));
  const mti=(monthlyPayment*12)/Math.max(1e-9,income);
  const LcapMap=principalFromMonthly(Number(maxMonthly||0),Number(interest||0)/100,fixedMortgageYears);
  const LcapUser=principalFromMonthly(Number(maxMonthly||0),Number(interest||0)/100,Math.max(1,Number(mortgageYears||1)));
  const capGapBySA2=useMemo(()=>bySA2Latest.map(r=>{const P=r.MedianPrice_adj;const L_needed=P*(1-(Number(depositPct||0)/100));const gap=(L_needed-LcapMap)/Math.max(1e-9,P);return{SA2_CODE:r.SA2_CODE,gap,P,L_needed}}),[bySA2Latest,depositPct,LcapMap]);

  const S_priceAdj=useMemo(()=>fmtMoney(Math.round(priceAdj)),[priceAdj]);
  const S_depositTarget=useMemo(()=>fmtMoney(Math.round(depositTarget)),[depositTarget]);
  const S_income=useMemo(()=>fmtMoney(Math.round(income)),[income]);
  const rentAdjWeek=Number(focusRow?.MedianRent_week_adj||0);
  const rentAdjMonth=rentAdjWeek*52/12;
  const rtiUser=(rentAdjWeek*52)/Math.max(1e-9,income);
  const S_rentAdjWeek=useMemo(()=>fmtMoney(Math.round(rentAdjWeek)),[rentAdjWeek]);
  const S_rentAdjMonth=useMemo(()=>fmtMoney(Math.round(rentAdjMonth)),[rentAdjMonth]);

  function higherIsBad(m){return["Median Price","Median Rent","PTI","RTI","Payment Cap Gap"].includes(m)}
  function valueForMetric(row){if(!row)return NaN;if(metric==="Median Rent")return row.MedianRent_week_adj;if(metric==="Median Price")return row.MedianPrice_adj;if(metric==="Median Income")return row.MedianIncome_annual;if(metric==="PTI")return row.PTI;if(metric==="Payment Cap Gap"){const g=capGapBySA2.find(x=>x.SA2_CODE===row.SA2_CODE)?.gap;return g}return row.RTI}
  const metricValsRaw=bySA2Latest.map(valueForMetric).filter(v=>Number.isFinite(v));
  const minV=metricValsRaw.length?Math.min(...metricValsRaw):0;
  const maxV=metricValsRaw.length?Math.max(...metricValsRaw):1;
  const focusVal=valueForMetric(focusRow||{});

  function onCellEnter(e,code,val){try{const svg=e.currentTarget.ownerSVGElement;const rect=svg.getBoundingClientRect();setHover({x:e.clientX-rect.left+8,y:e.clientY-rect.top+8,code,val})}catch(err){}}
  function onCellMove(e){if(!hover)return;try{const svg=e.currentTarget.ownerSVGElement||e.currentTarget;const rect=svg.getBoundingClientRect();setHover(h=>h?{...h,x:e.clientX-rect.left+8,y:e.clientY-rect.top+8}:h)}catch(err){}}
  function onCellLeave(){setHover(null)}

  return(<div className="p-4 space-y-4">
    <h1 className="text-2xl font-semibold">🏠 Дэшборд доступности жилья — Sydney</h1>
    <div className="flex items-center gap-3 p-2 rounded-xl bg-white shadow w-max">
      <button className={`px-3 py-1 rounded-lg ${segment==='tenants'?'bg-gray-900 text-white':'bg-gray-100'}`} onClick={()=>setSegment('tenants')}>Аренда</button>
      <button className={`px-3 py-1 rounded-lg ${segment==='buyers'?'bg-gray-900 text-white':'bg-gray-100'}`} onClick={()=>setSegment('buyers')}>Покупка</button>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <div className="col-span-1 space-y-3 p-4 rounded-2xl shadow bg-white">
        <h2 className="font-medium">Карта: слой</h2>
        <select className="w-full border rounded p-2" value={metric} onChange={e=>setMetric(e.target.value)}>
          <option>RTI</option><option>PTI</option><option>Median Rent</option>
          <option>Median Price</option><option>Median Income</option><option>Payment Cap Gap</option>
        </select>
        <label className="text-sm">Спален: {bedrooms}</label>
        <input type="range" min={1} max={3} value={bedrooms} onChange={e=>setBedrooms(+e.target.value)}/>
        <div className="flex items-center gap-2 mt-2">
          <input id="realgeo" type="checkbox" className="scale-110" checked={useRealGeo} onChange={e=>setUseRealGeo(e.target.checked)}/>
          <label htmlFor="realgeo" className="text-sm">Реальные SA2 полигоны</label>
          {useRealGeo&&(<span className="text-xs ml-2 px-2 py-0.5 rounded bg-gray-100">
            {geoStatus==='loading'&&'загрузка…'}{geoStatus==='ready'&&'готово'}{geoStatus==='error'&&'ошибка — сетка'}
          </span>)}
        </div>
        <hr className="my-2"/>
        <h2 className="font-medium">Период</h2>
        <select className="w-full border rounded p-2" value={preset} onChange={e=>setPreset(e.target.value)}>
          <option value="Max">Max</option><option value="5y">5 лет</option><option value="3y">3 года</option><option value="1y">1 год</option>
        </select>
        <hr className="my-2"/>
        <h2 className="font-medium">Сравнение районов</h2>
        <div className="space-y-2 max-h-48 overflow-auto border rounded p-2">
          {sa2.map(s=>(
            <label key={s.code} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={selected.includes(s.code)} onChange={()=>{
                if(selected.includes(s.code)) setSelected(selected.filter(x=>x!==s.code));
                else if(selected.length<3) setSelected([...selected,s.code]);
              }}/>
              {s.code}
            </label>
          ))}
        </div>
      </div>

      <div className="col-span-3 p-4 rounded-2xl shadow bg-white">
        <h2 className="font-medium mb-2">🗺️ SA2 слой {useRealGeo?"(реальный)":"(сетка)"}</h2>
        {!useRealGeo||!geojson?(
          <div className="relative">
            <svg viewBox="0 0 400 300" className="w-full h-[340px] rounded-xl border" onMouseMove={onCellMove}>
              {sa2.map(s=>{const w=400/4,h=300/3,x=s.c*w,y=s.r*h;
                const row=bySA2Latest.find(r=>r.SA2_CODE===s.code);
                const val=valueForMetric(row||{});
                const color=colorGYR(val,minV,maxV,!higherIsBad(metric));
                const focus=s.code===focusSA2;
                return(<g key={s.code} onClick={()=>setFocusSA2(s.code)}
                  onMouseEnter={e=>onCellEnter(e,s.code,fmtMetric(metric,val))} onMouseLeave={onCellLeave} style={{cursor:'pointer'}}>
                  <rect x={x+2} y={y+2} width={w-4} height={h-4} rx={8} fill={color} stroke={focus?"#111":"#fff"} strokeWidth={focus?3:2}/>
                  <text x={x+w/2} y={y+h/2} textAnchor="middle" dominantBaseline="middle" fontSize="12" fill="#000" style={{userSelect:'none'}}>{s.code}</text>
                </g>);
              })}
            </svg>
            {hover&&(<div className="absolute pointer-events-none bg-white/95 border rounded-lg shadow px-2 py-1 text-xs" style={{left:hover.x,top:hover.y}}>
              <div><b>{hover.code}</b></div><div>{metric}: <b>{hover.val}</b></div><div>Дата: {lastMonthStr}</div>
            </div>)}
          </div>
        ):(
          <>
            <GeoMapSA2 geojson={geojson} metric={metric} bedrooms={bedrooms} depositPct={depositPct}
              interest={interest} maxMonthly={maxMonthly} lastMonthStr={lastMonthStr}
              onHover={setHover} onLeave={()=>setHover(null)} onFocus={setFocusSA2}/>
            {hover&&(<div className="relative">
              <div className="absolute pointer-events-none bg-white/95 border rounded-lg shadow px-2 py-1 text-xs" style={{left:Math.max(0,hover.x),top:Math.max(0,hover.y)}}>
                <div><b>{hover.code}</b></div><div>{metric}: <b>{hover.val}</b></div><div>Дата: {lastMonthStr}</div>
              </div>
            </div>)}
          </>
        )}
        <div className="text-xs opacity-70 mt-1">Метрика: <b>{metric}</b>. Фокус: <b>{focusSA2}</b> — <b>{fmtMetric(metric,focusVal)}</b>.</div>
      </div>
    </div>

    <div className="p-4 rounded-2xl shadow bg-white">
      <h2 className="font-medium mb-2">📊 Сравнение</h2>
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead><tr className="bg-gray-50">
            <th className="p-2 text-left">SA2</th><th className="p-2 text-right">Median Price</th>
            <th className="p-2 text-right">Median Rent ({bedrooms}BR,/нед)</th>
            <th className="p-2 text-right">Income</th><th className="p-2 text-right">PTI</th>
            <th className="p-2 text-right">RTI</th><th className="p-2 text-right">Cap Gap</th>
          </tr></thead>
          <tbody>
            {bySA2Latest.filter(r=>selected.includes(r.SA2_CODE)).map(r=>{
              const gap=capGapBySA2.find(x=>x.SA2_CODE===r.SA2_CODE)?.gap;
              return(<tr key={r.SA2_CODE} className="border-t">
                <td className="p-2">{r.SA2_CODE}</td>
                <td className="p-2 text-right">{fmtMoney(Math.round(r.MedianPrice_adj))}</td>
                <td className="p-2 text-right">{fmtMoney(Math.round(r.MedianRent_week_adj))}</td>
                <td className="p-2 text-right">{fmtMoney(Math.round(r.MedianIncome_annual))}</td>
                <td className="p-2 text-right">{r.PTI.toFixed(1)}</td>
                <td className="p-2 text-right">{(r.RTI*100).toFixed(1)}%</td>
                <td className="p-2 text-right">{Number.isFinite(gap)?(gap<=0?"✅":"❌")+" "+(gap*100).toFixed(1)+"%":"—"}</td>
              </tr>)})}
          </tbody>
        </table>
      </div>
    </div>

    {segment==='buyers'
      ? <BuyerPanel {...{priceAdj,income,setIncomeUser,savings,setSavings,depositPct,setDepositPct,interest,setInterest,mortgageYears,setMortgageYears,S_priceAdj,S_depositTarget,S_income,LcapMap,LcapUser,maxMonthly,setMaxMonthly,targetMTI,setTargetMTI,mti}}/>
      : <TenantPanel {...{focusSA2,bedrooms,rentAdjWeek,rentAdjMonth,rtiUser,S_rentAdjWeek,S_rentAdjMonth,incomeUser,setIncomeUser}}/>}

    <div className="p-4 rounded-2xl shadow bg-white">
      <h2 className="font-medium mb-2">📈 Динамика</h2>
      {segment==='tenants'
        ? (<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ChartBlock title={`Median Rent (${bedrooms}BR, месяц)`} seriesKey="RentMonthly" ts={tsWithMedian(rows,months,startIndex,bedrooms,selected,sa2)} colorizer={(v,min,max)=>colorGYR(v,min,max,true)}/>
            <ChartBlock title="RTI" seriesKey="RTI" ts={tsWithMedian(rows,months,startIndex,bedrooms,selected,sa2)} thresholds={{green:[0,.25],amber:[.25,.30],red:[.30,1]}} colorizer={(v,min,max)=>colorGYR(v,min,max,true)}/>
          </div>)
        : (<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ChartBlock title={`Median Rent (${bedrooms}BR, неделя)`} seriesKey="Rent" ts={tsWithMedian(rows,months,startIndex,bedrooms,selected,sa2)} colorizer={(v,min,max)=>colorGYR(v,min,max,true)}/>
            <ChartBlock title="Median Price" seriesKey="Price" ts={tsWithMedian(rows,months,startIndex,bedrooms,selected,sa2)} colorizer={(v,min,max)=>colorGYR(v,min,max,true)}/>
            <ChartBlock title="PTI" seriesKey="PTI" ts={tsWithMedian(rows,months,startIndex,bedrooms,selected,sa2)} thresholds={{green:[0,8],amber:[8,10],red:[10,99]}} colorizer={(v,min,max)=>colorGYR(v,min,max,true)}/>
            <ChartBlock title="RTI" seriesKey="RTI" ts={tsWithMedian(rows,months,startIndex,bedrooms,selected,sa2)} thresholds={{green:[0,.25],amber:[.25,.30],red:[.30,1]}} colorizer={(v,min,max)=>colorGYR(v,min,max,true)}/>
          </div>)}
    </div>

    <div className="text-xs opacity-70">Данные синтетические.</div>
  </div>);
}

function BuyerPanel(p){const{priceAdj,income,setIncomeUser,savings,setSavings,depositPct,setDepositPct,interest,setInterest,mortgageYears,setMortgageYears,S_priceAdj,S_depositTarget,S_income,LcapMap,LcapUser,maxMonthly,setMaxMonthly,targetMTI,setTargetMTI,mti}=p;const depositTarget=(Number(depositPct||0)/100)*Number(priceAdj||0);const loanPrincipal=Math.max(0,Number(priceAdj||0)-depositTarget);const monthlyPayment=annuityMonthly(loanPrincipal,Number(interest||0)/100,Math.max(1,Number(mortgageYears||1)));const monthly25=annuityMonthly(loanPrincipal,Number(interest||0)/100,25);const mti25=(monthly25*12)/Math.max(1e-9,Number(income||0));const[buyerMode,setBuyerMode]=useState('budget');const P_affordable=Number(LcapUser||0)/Math.max(1e-9,1-(Number(depositPct||0)/100));const incomeRequiredFixedSR=(monthlyPayment*12)/.25;return(<div className="p-4 rounded-2xl shadow bg-white"><h2 className="font-medium mb-2">🏡 Покупка</h2><div className="flex items-center gap-2 mb-3"><span className="text-sm mr-2">Режим:</span><button className={`px-3 py-1 rounded-lg text-sm ${buyerMode==='budget'?'bg-gray-900 text-white':'bg-gray-100'}`}onClick={()=>setBuyerMode('budget')}>По бюджету</button><button className={`px-3 py-1 rounded-lg text-sm ${buyerMode==='fixed25'?'bg-gray-900 text-white':'bg-gray-100'}`}onClick={()=>setBuyerMode('fixed25')}>25 лет → MTI</button><button className={`px-3 py-1 rounded-lg text-sm ${buyerMode==='termIncome'?'bg-gray-900 text-white':'bg-gray-100'}`}onClick={()=>setBuyerMode('termIncome')}>Срок→доход</button></div><div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm mb-3"><label className="p-3 rounded-xl bg-gray-50 flex flex-col">Доход /год<input className="border rounded p-2 mt-1"type="number"value={Number.isFinite(income)?income:''}onChange={e=>setIncomeUser(+e.target.value||0)}/></label><label className="p-3 rounded-xl bg-gray-50 flex flex-col">Накопления<input className="border rounded p-2 mt-1"type="number"value={Number.isFinite(savings)?savings:''}onChange={e=>setSavings(+e.target.value||0)}/><span className="text-xs opacity-70 mt-1">Идут на депозит</span></label>{buyerMode==='budget'&&(<label className="p-3 rounded-xl bg-gray-50 flex flex-col">Макс платёж (/мес)<input className="border rounded p-2 mt-1"type="number"value={Number.isFinite(maxMonthly)?maxMonthly:''}onChange={e=>setMaxMonthly(+e.target.value||0)}/><span className="text-xs opacity-70 mt-1">Месячный бюджет</span></label>)}</div><div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm mb-3"><label className="p-3 rounded-xl bg-gray-50 flex flex-col">Deposit %<input type="range"min={5}max={30}value={depositPct}onChange={e=>setDepositPct(+e.target.value)}/><div className="mt-1">{depositPct}%</div></label><label className="p-3 rounded-xl bg-gray-50 flex flex-col">Ставка %<input type="range"min={2}max={10}step={.1}value={interest}onChange={e=>setInterest(+e.target.value)}/><div className="mt-1">{Number(interest).toFixed(1)}%</div></label>{buyerMode!=='fixed25'?(<label className="p-3 rounded-xl bg-gray-50 flex flex-col">Срок (лет)<input type="range"min={1}max={30}value={mortgageYears}onChange={e=>setMortgageYears(+e.target.value)}/><div className="mt-1">{mortgageYears} лет</div></label>):(<div className="p-3 rounded-xl bg-gray-50 text-sm">Срок: 25 лет</div>)}</div>{buyerMode==='budget'&&(<div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm"><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Доступная цена</div><div className="font-semibold">{fmtMoney(Math.round(P_affordable))}</div><div className="text-xs opacity-70">Слой Cap Gap на карте</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Платёж</div><div className="font-semibold">{fmtMoney(Math.round(monthlyPayment))}/мес</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">MTI</div><div className="font-semibold">{(mti*100).toFixed(1)}%</div></div></div>)}{buyerMode==='fixed25'&&(<div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm"><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Платёж 25л</div><div className="font-semibold">{fmtMoney(Math.round(monthly25))}/мес</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">MTI</div><div className="font-semibold">{(mti25*100).toFixed(1)}%</div><div className="text-xs opacity-70">До 30% ок</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Цена</div><div className="font-semibold">{S_priceAdj}</div></div></div>)}{buyerMode==='termIncome'&&(<div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm"><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Нужен доход (25%)</div><div className="font-semibold">{fmtMoney(Math.round(incomeRequiredFixedSR))}</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Платёж</div><div className="font-semibold">{fmtMoney(Math.round(monthlyPayment))}/мес</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Цена</div><div className="font-semibold">{S_priceAdj}</div></div></div>)}<div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4"><div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm"><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Цена</div><div className="font-semibold">{S_priceAdj}</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Депозит</div><div className="font-semibold">{S_depositTarget}</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Доход</div><div className="font-semibold">{S_income}</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Платёж</div><div className="font-semibold">{fmtMoney(Math.round(buyerMode==='fixed25'?monthly25:monthlyPayment))}/мес</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">MTI</div><div className="font-semibold">{(((buyerMode==='fixed25'?mti25:mti)*100)).toFixed(1)}%</div></div></div><div className="p-3 rounded-xl bg-gray-50 text-sm"><div className="font-medium mb-1">Пояснение</div><div>{buyerMode==='budget'&&("Лимит /мес → где покупка вписывается")} {buyerMode==='fixed25'&&("Фикс 25 лет → доля дохода")} {buyerMode==='termIncome'&&("MTI=25% → какой доход нужен")}</div></div></div>{(buyerMode!=='termIncome'&&mti>=.40)&&<div className="mt-1 text-red-600 text-sm">MTI ≥ 40% — высокая нагрузка</div>}{(buyerMode!=='termIncome'&&mti>=.30&&mti<.40)&&<div className="mt-1 text-amber-600 text-sm">MTI 30–40% — повышенная</div>}</div>)}

function TenantPanel({focusSA2,bedrooms,rentAdjWeek,rentAdjMonth,rtiUser,S_rentAdjWeek,S_rentAdjMonth,incomeUser,setIncomeUser}){return(<div className="p-4 rounded-2xl shadow bg-white"><h2 className="font-medium mb-2">🏘️ Аренда — {focusSA2}</h2><div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm mb-3"><label className="p-3 rounded-xl bg-gray-50 flex flex-col">Доход /год<input className="border rounded p-2 mt-1"type="number"value={incomeUser}onChange={e=>setIncomeUser(+e.target.value||0)}/></label><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Аренда ({bedrooms}BR, нед)</div><div className="font-semibold">{S_rentAdjWeek}</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">Аренда ({bedrooms}BR, мес)</div><div className="font-semibold">{S_rentAdjMonth}</div></div><div className="p-3 rounded-xl bg-gray-50"><div className="opacity-60">RTI</div><div className="font-semibold">{(rtiUser*100).toFixed(1)}%</div></div></div>{rtiUser>=.30&&<div className="mt-2 text-red-600 text-sm">RTI ≥ 30% — стресс</div>}{rtiUser>=.25&&rtiUser<.30&&<div className="mt-2 text-amber-600 text-sm">RTI 25–30% — граница</div>}<div className="text-xs opacity-70 mt-2">RTI = (годовая аренда / доход). Коэф.: 1.00/1.35/1.75.</div></div>)}

function GeoMapSA2({geojson,metric,bedrooms,depositPct,interest,maxMonthly,lastMonthStr,onHover,onLeave,onFocus}){function hash32(str){let h=2166136261>>>0;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}function getName(p){return p?.SA2_NAME21||p?.SA2_NAME_2021||p?.SA2_NAME16||p?.SA2_NAME_2016||p?.SA2_NAME||p?.NAME||p?.id||'SA2'}function getCode(p){return p?.SA2_MAIN21||p?.SA2_MAINCODE_2021||p?.SA2_MAIN16||p?.SA2_MAINCODE_2016||p?.SA2_CODE||getName(p)}function higherIsBadLocal(m){return["Median Price","Median Rent","PTI","RTI","Payment Cap Gap"].includes(m)}const coordsAll=[];geojson.features.forEach(f=>{const g=f.geometry;if(!g)return;const push=c=>coordsAll.push(c);const walk=geom=>{const type=geom.type,cs=geom.coordinates;if(type==='Polygon')cs.forEach(r=>r.forEach(pt=>push(pt)));else if(type==='MultiPolygon')cs.forEach(poly=>poly.forEach(r=>r.forEach(pt=>push(pt))))};walk(g)});if(!coordsAll.length)return<div className="p-3 rounded-xl bg-gray-50">GeoJSON пуст</div>;const lons=coordsAll.map(c=>c[0]),lats=coordsAll.map(c=>c[1]);const minLon=Math.min(...lons),maxLon=Math.max(...lons),minLat=Math.min(...lats),maxLat=Math.max(...lats);const W=800,H=520,pad=10;const sx=(W-2*pad)/(maxLon-minLon),sy=(H-2*pad)/(maxLat-minLat);const s=Math.min(sx,sy);const proj=([lon,lat])=>[pad+(lon-minLon)*s,pad+(maxLat-lat)*s];const pathFromGeom=geom=>{const cs=geom.coordinates;let d="";if(geom.type==='Polygon'){cs.forEach(r=>{r.forEach((pt,i)=>{const[x,y]=proj(pt);d+=(i?`L${x},${y}`:`M${x},${y}`)});d+="Z"})}else if(geom.type==='MultiPolygon'){cs.forEach(poly=>{poly.forEach(r=>{r.forEach((pt,i)=>{const[x,y]=proj(pt);d+=(i?`L${x},${y}`:`M${x},${y}`)});d+="Z"})})}return d};const LcapMap=principalFromMonthly(Number(maxMonthly||0),Number(interest||0)/100,25);const RENT={1:1,2:1.35,3:1.75}[bedrooms]||1;const vals=geojson.features.map(f=>{const p=f.properties||{};const code=String(getCode(p));const name=getName(p);let seed=hash32(code);const rnd=()=>{seed|=0;seed=(seed+0x6D2B79F5)|0;let t=Math.imul(seed^seed>>>15,1|seed);t=(t+Math.imul(t^t>>>7,61|t))^t;return((t^t>>>14)>>>0)/4294967296};const price=600000+rnd()*900000;const rentW=380+rnd()*520;const income=65000+rnd()*60000;const P=price*({1:.85,2:1,3:1.25}[bedrooms]||1);const Rw=rentW*RENT;const I=income;const PTI=P/I;const RTI=(Rw*52)/I;const L_needed=P*(1-(Number(depositPct||0)/100));const gap=(L_needed-LcapMap)/Math.max(1e-9,P);const pick=metric==='Median Price'?P:metric==='Median Rent'?Rw:metric==='Median Income'?I:metric==='PTI'?PTI:metric==='Payment Cap Gap'?gap:RTI;return{name,code,value:pick,display:fmtMetric(metric,pick),geom:f.geometry}});const nums=vals.map(v=>v.value).filter(Number.isFinite);const vmin=Math.min(...nums),vmax=Math.max(...nums);const[scale,setScale]=useState(1);const[pan,setPan]=useState({x:0,y:0});const[drag,setDrag]=useState(null);const onWheel=e=>{e.preventDefault();const k=Math.exp(-e.deltaY*.001);setScale(s=>Math.max(.8,Math.min(8,s*k)))};const onMouseDown=e=>setDrag({x:e.clientX,y:e.clientY,pan0:{...pan}});c_*_
