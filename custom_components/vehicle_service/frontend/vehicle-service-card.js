/**
 * Vehicle Service Manager - Lovelace Cards
 * Includes: vehicle-service-card + vehicle-service-compact-card
 * Version is fetched from the backend (vehicle_service/version) at runtime.
 */

// ── LitElement / Base Resolution ──────────────────────────────────────────────
const _LitElement = () => {
  const el =
    customElements.get("ha-panel-lovelace") ||
    customElements.get("hui-view") ||
    customElements.get("home-assistant");
  return el ? Object.getPrototypeOf(Object.getPrototypeOf(el.prototype)).constructor : HTMLElement;
};

const DOMAIN = "vehicle_service";

// Version comes from the backend — single source of truth is manifest.json.
// Logged once (with the integration's styling) when the first card loads.
let _versionLogged = false;
async function fetchVersion(hass) {
  let ver = "unknown";
  try {
    const r = await hass.callWS({ type: `${DOMAIN}/version` });
    ver = (r && (r.version || (r.result && r.result.version))) || "unknown";
  } catch (e) { /* integration not loaded yet */ }
  if (ver !== "unknown" && !_versionLogged) {
    _versionLogged = true;
    console.info(
      "%c VEHICLE-SERVICE-CARD %c v" + ver + " ",
      "background:#1976D2;color:#fff;font-weight:bold",
      "background:#4CAF50;color:#fff"
    );
  }
  return ver;
}

// ── Brand Helpers & Theme Colors ──────────────────────────────────────────────
const BRAND_COLORS = {
  volkswagen: "#00519F", vw: "#00519F", skoda: "#4BA82E", audi: "#BB0A30", bmw: "#1C69D4",
  mercedes: "#9E9E9E", "mercedes-benz": "#9E9E9E", mini: "#000000", porsche: "#AE0521",
  opel: "#FFED00", ford: "#003476", seat: "#E2001A", cupra: "#1B1B1B", renault: "#FFCC00",
  peugeot: "#003189", fiat: "#9B0000", toyota: "#EB0A1E", honda: "#CC0000", mazda: "#910E10",
  nissan: "#C3002F", hyundai: "#002C5F", kia: "#05141F", volvo: "#003057", tesla: "#CC0000",
  dacia: "#005BBB", citroen: "#9E1B32",
};

function brandColor(make) {
  return make ? BRAND_COLORS[make.toLowerCase().trim()] || "#1976D2" : "#1976D2";
}

function makeInitials(make) {
  if (!make) return "?";
  const words = make.trim().split(/\s+/);
  return words.length >= 2
    ? (words[0][0] + words[1][0]).toUpperCase()
    : make.slice(0, 2).toUpperCase();
}

function logoHtml(make, size = 20) {
  const color = brandColor(make);
  const initials = makeInitials(make);
  const fontSize = size <= 16 ? Math.round(size * 0.5) : Math.round(size * 0.42);
  const borderRadius = size <= 20 ? "50%" : "8px";

  return `<div style="
    width: ${size}px;
    height: ${size}px;
    border-radius: ${borderRadius};
    background: ${color};
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: ${fontSize}px;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
    letter-spacing: -0.5px;
  ">${initials}</div>`;
}

// ── i18n & Localization ────────────────────────────────────────────────────────
const I18N = {
  en: {
    subtitle: "Service status, repairs and tire tracking",
    errorPrefix: "Error: ",
    error: "Error",
    noVehicles: "No vehicles.",
    noVehiclesHint: "Settings → Integrations → + → Vehicle Service Manager",
    ok: "OK",
    tabStatus: "Service status",
    tabHistory: "Service history",
    tabRepairs: "Repairs",
    tabTires: "Tires",
    loading: "Loading…",
    regDate: "Reg.",
    liveKm: "Live KM",
    updateKm: "Update mileage",
    odometer: "Mileage",
    soon: "Due soon",
    due: "Due",
    noServices: "No service points configured.",
    noEntry: "No entry",
    overdue: "Overdue",
    dueSoon: "Due soon",
    inSight: "In sight",
    kmOverdue: "km overdue",
    timeExpired: "Time expired",
    months: "mo",
    entries: "Entries",
    addEntry: "+ Entry",
    noEntries: "No entries yet.",
    repairs: "Repairs",
    addRepair: "+ Add",
    noRepairs: "No repairs yet.",
    noTires: "No tires recorded yet.",
    critical: "Critical!",
    criticalShort: "Critical",
    borderline: "Borderline",
    borderlineShort: "Borderline",
    wearNote: "Wear: 1.5 mm / 10,000 km · Rec. limit: {wm} mm · Min.: 1.6 mm",
    currentlyMounted: "Currently mounted",
    addTire: "+ Record tires",
    tireHistory: "Tire history",
    serviceEntry: "Service entry",
    km: "KM",
    work: "Work",
    notes: "Notes",
    workshopPh: "Workshop...",
    save: "Save",
    repair: "Repair",
    category: "Category",
    description: "Description",
    repairPh: "e.g. brake pads",
    cost: "Cost €",
    enterTires: "Record tires",
    type: "Type",
    axle: "Axle",
    size: "Size",
    brand: "Brand",
    treadDepth: "Tread depth",
    editEntry: "Edit entry",
    update: "Update",
    confirmDeleteEntry: "Delete entry?",
    confirmDelete: "Delete?",
    enterDate: "Please enter a date.",
    selectService: "Please select a service point.",
    week: "Wk",
  },
};

function _lang(hass) {
  return (((hass && hass.language) || navigator.language || "en") + "")
    .toLowerCase()
    .slice(0, 2) || "en";
}

function t(hass, key) {
  const lang = _lang(hass);
  const dict = I18N[lang];
  return dict && dict[key] != null
    ? dict[key]
    : I18N.en[key] != null
    ? I18N.en[key]
    : key;
}

function _loc(hass) {
  return (hass && hass.language) || navigator.language || "en";
}

const SVC_LABELS = {
  en: { oil: "Oil change", inspection: "Inspection", brake_fluid: "Brake fluid", cabin_filter: "Cabin filter", air_filter: "Air filter", spark_plugs: "Spark plugs", fuel_filter: "Fuel filter", gearbox: "Gearbox oil", haldex: "Haldex oil", ac: "A/C service", hu: "MOT (HU/AU)" },
};

function svcLabel(hass, sid) {
  const labels = SVC_LABELS[_lang(hass)] || SVC_LABELS.en;
  return labels[sid] || sid;
}

const SVC_ICONS = {
  oil: "mdi:oil", inspection: "mdi:clipboard-check-outline", brake_fluid: "mdi:car-brake-alert",
  cabin_filter: "mdi:fan", air_filter: "mdi:air-filter", spark_plugs: "mdi:lightning-bolt",
  fuel_filter: "mdi:gas-station", gearbox: "mdi:cog-transfer", haldex: "mdi:car-4wd",
  ac: "mdi:air-conditioner", hu: "mdi:car-search",
};

const REP_LABELS = {
  en: {
    brakes_front: "Front brakes", brakes_rear: "Rear brakes", brakes_full: "Full brake service",
    discs_front: "Front discs", discs_rear: "Rear discs", shock_front: "Front shocks",
    shock_rear: "Rear shocks", timing_belt: "Timing belt", battery: "Battery", clutch: "Clutch", other: "Other",
  },
};

function repLabel(hass, cat) {
  const labels = REP_LABELS[_lang(hass)] || REP_LABELS.en;
  return labels[cat] || cat;
}

const TIRE_TYPES = {
  en: { summer: "Summer", winter: "Winter", allseason: "All-season" },
};
function tireTypeLabel(hass, tt) {
  const labels = TIRE_TYPES[_lang(hass)] || TIRE_TYPES.en;
  return labels[tt] || tt;
}

const AXLES = {
  en: { all: "All four", front: "Front", rear: "Rear" },
};
function axleLabel(hass, ax) {
  const labels = AXLES[_lang(hass)] || AXLES.en;
  return labels[ax] || ax;
}

const WHEEL_POS = {
  en: ["FL", "FR", "RL", "RR"],
};
function wheelPos(hass) {
  return WHEEL_POS[_lang(hass)] || WHEEL_POS.en;
}

const TIRE_WARN = { summer: 3.0, winter: 4.0, allseason: 4.0 };
const TIRE_MIN = 1.6;
const WEAR = 1.5 / 10000;

function calcPct(vehicle, sid) {
  const last = (vehicle.lastService || {})[sid] || {};
  const intv = (vehicle.intervals || {})[sid] || {};
  const ez = vehicle.ezDate;
  const curKm = vehicle.km || 0;

  let kp = null, kl = null, tp = null, ml = null;

  if (intv.km) {
    const base = last.km != null ? last.km : 0;
    const driven = curKm - base;
    kp = Math.min(100, Math.round((driven / intv.km) * 100));
    kl = Math.max(0, intv.km - driven);
  }

  if (intv.months) {
    const baseDate = last.date || ez || null;
    if (baseDate) {
      const ms = (Date.now() - new Date(baseDate).getTime()) / (1000 * 60 * 60 * 24 * 30.44);
      tp = Math.min(100, Math.round((ms / intv.months) * 100));
      ml = Math.max(0, Math.round(intv.months - ms));
    } else {
      tp = 0;
      ml = intv.months;
    }
  }

  const pct = Math.max(kp ?? 0, tp ?? 0);
  const isRed = pct >= 90 || (kl !== null && kl <= 1000) || (ml !== null && ml <= 1);
  const isYellow = !isRed && (pct >= 70 || (kl !== null && kl <= 3000) || (ml !== null && ml <= 3));

  return { pct, kp, tp, kl, ml, tier: isRed ? "red" : isYellow ? "yellow" : "green" };
}

const TIER_COL = { green: "#3B6D11", yellow: "#BA7517", red: "#A32D2D" };
const TIER_BG = { green: "#EAF3DE", yellow: "#FAEEDA", red: "#FCEBEB" };

function fd(iso, hass) {
  return iso ? new Date(iso).toLocaleDateString(_loc(hass)) : "—";
}

function fkm(km, hass) {
  return km != null ? Number(km).toLocaleString(_loc(hass)) + " km" : "—";
}

function today() {
  return new Date().toISOString().split("T")[0];
}

const WIDTHS = [135, 145, 155, 165, 175, 185, 195, 205, 215, 225, 235, 245, 255, 265, 275, 285, 295, 305, 315, 325, 335];
const RATIOS = [25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80];
const RIMS = [13, 14, 15, 16, 17, 18, 19, 20, 21, 22];
const PROF_STEPS = Array.from({ length: 25 }, (_, i) => parseFloat((i * 0.5).toFixed(1)));

function sel(id, opts, val = "") {
  return `<select id="${id}">${opts.map((o) => `<option value="${o.v || o}" ${(o.v || o) == val ? "selected" : ""}>${o.l || o}</option>`).join("")}</select>`;
}

function inp(id, type, ph, val = "", extra = "") {
  return `<input id="${id}" type="${type}" placeholder="${ph}" value="${val}" ${extra}/>`;
}

// ── Full Card ──────────────────────────────────────────────────────────────────
class VehicleServiceCard extends HTMLElement {
  constructor(){super();this.attachShadow({mode:"open"});this._hass=null;this._vehicles=[];this._vehicleIds=[];this._cur=0;this._tab="status";this._loading=true;this._err=null;this._modal=null;}
  setConfig(c){this._config=c;}
  set hass(h){const first=!this._hass;this._hass=h;if(first&&h)this._load();}
  static getStubConfig(){return{};}
  static getConfigElement(){return document.createElement("vehicle-service-card-editor");}
  getCardSize(){return 8;}

  async _load(){
    this._loading=true;this._err=null;this._paint();
    try{const r=await this._hass.callWS({type:`${DOMAIN}/vehicles`});const e=Object.entries(r.vehicles||{});this._vehicleIds=e.map(([id])=>id);this._vehicles=e.map(([,v])=>v);this._version=await fetchVersion(this._hass);this._loading=false;}
    catch(e){this._err=`${e.message||e}`;this._loading=false;}
    this._paint();
  }
  async _ws(msg){try{await this._hass.callWS(msg);await this._load();}catch(e){alert(t(this._hass,"errorPrefix")+(e.message||e));await this._load();}}
  _v(){return this._vehicles[this._cur];}
  _vid(){return this._vehicleIds[this._cur];}

  _placeholder(){
    return '<div style="padding:16px">'
      +'<div style="font-size:14px;font-weight:500;margin-bottom:8px">Vehicle Service Manager</div>'
      +'<div style="font-size:11px;color:#888;margin-bottom:10px">'+t(this._hass,"subtitle")+'</div>'
      +'<div style="display:flex;gap:6px">'
      +['mdi:oil','mdi:clipboard-check-outline','mdi:car-brake-alert','mdi:fan'].map(function(i){
        return '<div style="background:#EAF3DE;border-radius:8px;width:36px;height:36px;display:flex;align-items:center;justify-content:center"><ha-icon icon="'+i+'" style="color:#3B6D11;--mdc-icon-size:20px"></ha-icon></div>';
      }).join("")
      +'</div></div>';
  }

  _paint(){
    let body="";
    const h=this._hass;
    if(!h){body=this._placeholder();}
    else if(this._loading)body=`<div class="loading"><div class="spin"></div>${t(h,"loading")}</div>`;
    else if(this._err)body=`<div class="errbox"><b>${t(h,"error")}</b><br>${this._err}</div>`;
    else if(!this._vehicles.length)body=`<div class="empty-big">${t(h,"noVehicles")}<br><b>${t(h,"noVehiclesHint")}</b></div>`;
    else body=this._main();
    this.shadowRoot.innerHTML=`<style>${this._css()}</style><ha-card><div class="w">${body}${this._modal||""}</div></ha-card>`;
    this._bind();
  }

  _main(){return this._pills()+this._vhdr()+this._metrics()+this._tabbar()+this._content();}

  _pills(){return`<div class="pills">${this._vehicles.map((v,i)=>`<button class="pill${i===this._cur?" on":""}" data-i="${i}">${logoHtml(v.make||"",16)}${v.make||""} ${v.model||""}</button>`).join("")}</div>`;}

  _vhdr(){const v=this._v();const h=this._hass;return`<div class="vhdr">${logoHtml(v.make||"",34)}<div><div class="vtit">${v.make||""} ${v.model||""}</div><div class="vmeta">${v.plate?`<span class="chip">${v.plate}</span>`:""}${v.ezDate?`<span class="chip">${t(h,"regDate")} ${fd(v.ezDate,h)}</span>`:""}${v.entity?`<span class="chip live">\u2B24 ${t(h,"liveKm")}</span>`:""}</div></div></div>`;}

  _metrics(){
    const v=this._v();let ok=0,warn=0,crit=0;
    for(const sid of(v.services||[])){const{tier}=calcPct(v,sid);if(tier==="green")ok++;else if(tier==="yellow")warn++;else crit++;}
    const h=this._hass;
    return`<div class="mets"><div class="met" style="cursor:pointer" id="met-km" title="${t(h,"updateKm")}"><div class="ml">${t(h,"odometer")} \u270E</div><div class="mv">${fkm(v.km,h)}</div></div><div class="met"><div class="ml" style="color:#3B6D11">\u2713 ${t(h,"ok")}</div><div class="mv" style="color:#3B6D11">${ok}</div></div><div class="met"><div class="ml" style="color:#BA7517">\u26A1 ${t(h,"soon")}</div><div class="mv" style="color:#BA7517">${warn}</div></div><div class="met"><div class="ml" style="color:#A32D2D">\u26A0 ${t(h,"due")}</div><div class="mv" style="color:#A32D2D">${crit}</div></div></div>`;
  }

  _tabbar(){const h=this._hass;const tabs=[{id:"status",l:t(h,"tabStatus")},{id:"history",l:t(h,"tabHistory")},{id:"repairs",l:t(h,"tabRepairs")},{id:"tires",l:t(h,"tabTires")}];return`<div class="tabbar">${tabs.map(tb=>`<button class="tab${this._tab===tb.id?" on":""}" data-tab="${tb.id}">${tb.l}</button>`).join("")}</div>`;}

  _content(){const v=this._v();if(this._tab==="status")return this._status(v);if(this._tab==="history")return this._history(v);if(this._tab==="repairs")return this._repairs(v);if(this._tab==="tires")return this._tires(v);return"";}

  _status(v){
    const h=this._hass;
    if(!(v.services||[]).length)return`<div class="tc"><div class="empty">${t(h,"noServices")}</div></div>`;
    return`<div class="tc">${(v.services||[]).map(sid=>{
      const r=calcPct(v,sid),last=(v.lastService||{})[sid]||{},col=TIER_COL[r.tier],bg=TIER_BG[r.tier];
      const lastStr=last.date?`${fd(last.date,h)}${last.km?" \u00B7 "+fkm(last.km,h):""}`:v.ezDate?`${t(h,"noEntry")} \u2013 ${t(h,"regDate")} ${fd(v.ezDate,h)}`:t(h,"noEntry");
      const statusLbl=r.tier==="red"?(r.pct>=100?t(h,"overdue"):t(h,"dueSoon")):r.tier==="yellow"?t(h,"inSight"):t(h,"ok");
      const parts=[];if(r.kl!==null)parts.push(r.kl<=0?t(h,"kmOverdue"):fkm(r.kl,h));if(r.ml!==null)parts.push(r.ml<=0?t(h,"timeExpired"):r.ml+" "+t(h,"months"));
      return`<div class="srow"><div class="sico" style="background:${bg};color:${col}"><ha-icon icon="${SVC_ICONS[sid]||"mdi:wrench"}"></ha-icon></div><div class="sbod"><div class="snm">${svcLabel(h,sid)}</div><div class="slt">${lastStr}</div><div class="pbar"><div class="pfil" style="width:${r.pct}%;background:${col}"></div></div></div><div class="srt"><span class="badge" style="background:${bg};color:${col}">${statusLbl}</span><div class="ssub">${parts.join(" \u00B7 ")}</div></div></div>`;
    }).join("")}</div>`;
  }

  _history(v){
    const h=this._hass;
    const hist=[...(v.history||[])].sort((a,b)=>new Date(b.date)-new Date(a.date));
    const rows=hist.map((he,i)=>{
      const chips=(he.services||[]).map(sid=>`<span class="chip2"><ha-icon icon="${SVC_ICONS[sid]||"mdi:wrench"}" style="--mdc-icon-size:11px"></ha-icon>${svcLabel(h,sid)}</span>`).join("");
      const editBtn=he.auto?"":`<button class="ibtn edit-svc" data-idx="${i}">\u270E</button>`;
      return`<div class="hrow"><div class="hd">${fd(he.date,h)}${he.auto?`<span class="atag">auto</span>`:""}<div class="hkm">${fkm(he.km,h)}</div></div><div class="hb">${he.notes?`<div class="hn">${he.notes}</div>`:""}<div class="chrow">${chips}</div></div><div style="display:flex;gap:2px">${editBtn}<button class="ibtn del-svc" data-idx="${i}">\u2715</button></div></div>`;
    }).join("");
    return`<div class="tc"><div class="shdr"><span>${t(h,"entries")}</span><button class="addbtn" id="btn-svc">${t(h,"addEntry")}</button></div>${rows||`<div class="empty">${t(h,"noEntries")}</div>`}</div>`;
  }

  _repairs(v){
    const h=this._hass;
    const reps=[...(v.repairs||[])].sort((a,b)=>new Date(b.date)-new Date(a.date));
    const rows=reps.map((r,i)=>`<div class="rrow"><div class="rico"><ha-icon icon="mdi:wrench"></ha-icon></div><div class="rbod"><div class="rnm">${repLabel(h,r.cat)}</div>${r.desc?`<div class="rdsc">${r.desc}</div>`:""}<div class="rmt">${fd(r.date,h)}${r.km?" \u00B7 "+fkm(r.km,h):""}</div></div>${r.cost?`<div class="rco">${parseFloat(r.cost).toLocaleString(_loc(h),{minimumFractionDigits:0})} \u20AC</div>`:""}<button class="ibtn del-rep" data-idx="${i}">\u2715</button></div>`).join("");
    return`<div class="tc"><div class="shdr"><span>${t(h,"repairs")}</span><button class="addbtn" id="btn-rep">${t(h,"addRepair")}</button></div>${rows||`<div class="empty">${t(h,"noRepairs")}</div>`}</div>`;
  }

  _tires(v){
    const h=this._hass;
    const curKm=v.km||0,tires=v.tires||[],history=[...tires].sort((a,b)=>new Date(b.date)-new Date(a.date)),latest=tires.length?tires[tires.length-1]:null;
    const wp=wheelPos(h);
    let currentHtml=`<div class="empty">${t(h,"noTires")}</div>`;
    if(latest){
      const tt=latest.type||"summer",wm=TIRE_WARN[tt]||3,mKm=parseInt(latest.km)||0;
      const sz=latest.width&&latest.ratio&&latest.rim?`${latest.width}/${latest.ratio} R${latest.rim}`:"";
      const tLbl=tireTypeLabel(h,tt);
      let worst=999;["vl","vr","hl","hr"].forEach(pos=>{const orig=parseFloat(latest[pos])||0;if(orig){const worn=Math.max(0,orig-Math.max(0,curKm-mKm)*WEAR);if(worn<worst)worst=worn;}});
      const oc=worst<=TIRE_MIN?"#A32D2D":worst<=wm?"#BA7517":"#3B6D11",ol=worst<=TIRE_MIN?t(h,"critical"):worst<=wm?t(h,"borderline"):t(h,"ok");
      const wheels=["vl","vr","hl","hr"].map((pos,i)=>{
        const orig=parseFloat(latest[pos])||0;
        if(!orig)return`<div class="tw"><div class="twp">${wp[i]}</div><div class="twv" style="color:var(--secondary-text-color)">\u2014</div></div>`;
        const driven=Math.max(0,curKm-mKm),worn=Math.max(0,orig-driven*WEAR).toFixed(1);
        const col=worn<=TIRE_MIN?"#A32D2D":worn<=wm?"#BA7517":"#3B6D11",lbl=worn<=TIRE_MIN?t(h,"criticalShort"):worn<=wm?t(h,"borderlineShort"):t(h,"ok");
        const pct=Math.min(100,Math.max(0,(worn/orig)*100)),kml=Math.round(Math.max(0,(worn-wm)/WEAR));
        return`<div class="tw"><div class="twp">${wp[i]}</div><div class="twv" style="color:${col}">${worn} mm</div><div class="twbar"><div style="width:${pct}%;background:${col};height:100%;border-radius:2px"></div></div><div class="twl" style="color:${col}">${lbl}</div>${worn>wm?`<div class="twkm">~${kml.toLocaleString(_loc(h))} km</div>`:""}</div>`;
      }).join("");
      currentHtml=`<div class="tire-status-header"><div class="tire-type-badge" style="background:${oc}20;color:${oc};border:1px solid ${oc}40">${tLbl}</div><div style="color:${oc};font-size:12px;font-weight:500">\u25CF ${ol}</div></div><div class="tire-info-row">${sz?`<span class="ms mono">${sz}</span>`:""} ${latest.brand?`<span class="ms">${latest.brand}</span>`:""}</div><div class="tgrid">${wheels}</div><div class="tnote">${t(h,"wearNote").replace("{wm}",String(wm))}</div>`;
    }
    const histRows=history.map((th,i)=>{const tt=th.type||"summer";const tLbl=tireTypeLabel(h,tt);const sz=th.width&&th.ratio&&th.rim?`${th.width}/${th.ratio} R${th.rim}`:"";return`<div class="hrow" style="grid-template-columns:100px 1fr auto"><div class="hd">${fd(th.date,h)}<div class="hkm">${fkm(th.km,h)}</div></div><div class="hb"><div style="font-size:12px;font-weight:500">${tLbl}${sz?` \u00B7 <span style="font-family:monospace">${sz}</span>`:""}</div>${th.brand?`<div style="font-size:11px;color:var(--secondary-text-color)">${th.brand}</div>`:""}</div><button class="ibtn del-tire" data-idx="${i}">\u2715</button></div>`;}).join("");
    return`<div class="tc"><div class="shdr"><span>${t(h,"currentlyMounted")}</span><button class="addbtn" id="btn-tire">${t(h,"addTire")}</button></div><div class="tcard">${currentHtml}</div>${history.length>1?`<div class="shdr" style="margin-top:14px"><span>${t(h,"tireHistory")}</span></div>${histRows}`:""}</div>`;
  }

  _showSvcModal(){const v=this._v();const h=this._hass;const svcs=(v.services||[]).map(sid=>`<label class="cblabel"><input type="checkbox" class="svc-cb" value="${sid}"> ${svcLabel(h,sid)}</label>`).join("");this._modal=`<div class="overlay" id="modal"><div class="mbox"><div class="mhdr">${t(h,"serviceEntry")} <button class="closebtn" id="mclose">\u2715</button></div><div class="mrow2">${inp("m-date","date","",today())} ${inp("m-km","number",t(h,"km"),v.km||"")}</div><div class="mfld"><label>${t(h,"work")}</label><div class="cbgrid">${svcs}</div></div><div class="mfld"><label>${t(h,"notes")}</label>${inp("m-notes","text",t(h,"workshopPh"))}</div><div class="mbtn-row"><button class="sbtn" id="m-save-svc">${t(h,"save")}</button></div></div></div>`;this._paint();}
  _showRepModal(){const v=this._v();const h=this._hass;const catOpts=Object.entries(REP_LABELS[_lang(h)]||REP_LABELS.en).map(([k,l])=>({v:k,l}));this._modal=`<div class="overlay" id="modal"><div class="mbox"><div class="mhdr">${t(h,"repair")} <button class="closebtn" id="mclose">\u2715</button></div><div class="mrow2">${inp("r-date","date","",today())} ${inp("r-km","number",t(h,"km"),v.km||"")}</div><div class="mfld"><label>${t(h,"category")}</label>${sel("r-cat",catOpts)}</div><div class="mfld"><label>${t(h,"description")}</label>${inp("r-desc","text",t(h,"repairPh"))}</div><div class="mfld"><label>${t(h,"cost")}</label>${inp("r-cost","number","0")}</div><div class="mbtn-row"><button class="sbtn" id="m-save-rep">${t(h,"save")}</button></div></div></div>`;this._paint();}
  _showTireModal(){const v=this._v();const h=this._hass;const wp=wheelPos(h);const wOpts=WIDTHS.map(w=>({v:w,l:w})),rOpts=RATIOS.map(r=>({v:r,l:r})),rimOpts=RIMS.map(r=>({v:r,l:r})),pOpts=PROF_STEPS.map(p=>({v:p,l:p.toFixed(1)+" mm"}));this._modal=`<div class="overlay" id="modal"><div class="mbox"><div class="mhdr">${t(h,"enterTires")} <button class="closebtn" id="mclose">\u2715</button></div><div class="mrow2">${inp("t-date","date","",today())} ${inp("t-km","number",t(h,"km"),v.km||"")}</div><div class="mrow2"><div class="mfld"><label>${t(h,"type")}</label>${sel("t-type",[{v:"summer",l:tireTypeLabel(h,"summer")},{v:"winter",l:tireTypeLabel(h,"winter")},{v:"allseason",l:tireTypeLabel(h,"allseason")}])}</div><div class="mfld"><label>${t(h,"axle")}</label>${sel("t-axle",[{v:"all",l:axleLabel(h,"all")},{v:"front",l:axleLabel(h,"front")},{v:"rear",l:axleLabel(h,"rear")}])}</div></div><div class="mfld"><label>${t(h,"size")}</label><div class="sizerow">${sel("t-w",wOpts,"205")}<span class="sep">/</span>${sel("t-r",rOpts,"55")}<span class="sep">R</span>${sel("t-rim",rimOpts,"16")}</div><div class="sizeprev" id="sp">\u2192 205/55 R16</div></div><div class="mrow2"><div class="mfld"><label>${t(h,"brand")}</label>${inp("t-brand","text","Michelin")}</div><div class="mfld"><label>DOT</label>${inp("t-dot","text","2323","","maxlength='4'")}<div class="dotprev" id="dp"></div></div></div><div class="mfld"><label>${t(h,"treadDepth")}</label><div class="profgrid"><div><label class="plbl">${wp[0]}</label>${sel("t-vl",pOpts,"8.0")}</div><div><label class="plbl">${wp[1]}</label>${sel("t-vr",pOpts,"8.0")}</div><div><label class="plbl">${wp[2]}</label>${sel("t-hl",pOpts,"8.0")}</div><div><label class="plbl">${wp[3]}</label>${sel("t-hr",pOpts,"8.0")}</div></div></div><div class="mbtn-row"><button class="sbtn" id="m-save-tire">${t(h,"save")}</button></div></div></div>`;this._paint();}
  _showKmModal(){const v=this._v();const h=this._hass;this._modal=`<div class="overlay" id="modal"><div class="mbox" style="max-width:340px"><div class="mhdr">${t(h,"updateKm")} <button class="closebtn" id="mclose">\u2715</button></div><div class="mfld"><label>${t(h,"odometer")}</label><input id="km-val" type="number" value="${v.km||0}" style="width:100%;padding:10px;border-radius:8px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color);font-size:18px;font-weight:500;box-sizing:border-box;text-align:right"/></div><div class="mbtn-row"><button class="sbtn" id="m-save-km">${t(h,"save")}</button></div></div></div>`;this._paint();}
  _showEditSvcModal(hist,idx){const v=this._v(),he=hist[idx];const h=this._hass;const svcs=(v.services||[]).map(sid=>`<label class="cblabel"><input type="checkbox" class="svc-cb" value="${sid}" ${(he.services||[]).includes(sid)?"checked":""}> ${svcLabel(h,sid)}</label>`).join("");this._editIdx=idx;this._editHist=hist;this._modal=`<div class="overlay" id="modal"><div class="mbox"><div class="mhdr">${t(h,"editEntry")} <button class="closebtn" id="mclose">\u2715</button></div><div class="mrow2"><input id="m-date" type="date" value="${he.date}"/><input id="m-km" type="number" value="${he.km||0}"/></div><div class="mfld"><label>${t(h,"work")}</label><div class="cbgrid">${svcs}</div></div><div class="mfld"><label>${t(h,"notes")}</label><input id="m-notes" type="text" value="${he.notes||""}"/></div><div class="mbtn-row"><button class="sbtn" id="m-save-edit-svc">${t(h,"update")}</button></div></div></div>`;this._paint();}
  _closeModal(){this._modal=null;this._editIdx=null;this._editHist=null;this._paint();}

  _bind(){
    const s=this.shadowRoot;
    const h=this._hass;
    s.querySelectorAll(".pill").forEach(b=>b.addEventListener("click",()=>{this._cur=parseInt(b.dataset.i);this._paint();}));
    s.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{this._tab=b.dataset.tab;this._paint();}));
    s.getElementById("btn-svc")?.addEventListener("click",()=>this._showSvcModal());
    s.getElementById("btn-rep")?.addEventListener("click",()=>this._showRepModal());
    s.getElementById("btn-tire")?.addEventListener("click",()=>this._showTireModal());
    s.getElementById("mclose")?.addEventListener("click",()=>this._closeModal());
    s.getElementById("met-km")?.addEventListener("click",()=>this._showKmModal());
    s.getElementById("m-save-km")?.addEventListener("click",async()=>{const vid=this._vid(),km=parseInt(s.getElementById("km-val").value)||0;this._closeModal();await this._ws({type:`${DOMAIN}/update_km`,vehicle_id:vid,km});});
    s.querySelectorAll(".del-svc").forEach(b=>b.addEventListener("click",async()=>{if(!confirm(t(h,"confirmDeleteEntry")))return;const v=this._v(),vid=this._vid();const hist=[...(v.history||[])].sort((a,b2)=>new Date(b2.date)-new Date(a.date));const he=hist[parseInt(b.dataset.idx)];const ri=(v.history||[]).findIndex(x=>x.date===he.date&&x.km===he.km&&JSON.stringify(x.services)===JSON.stringify(he.services));await this._ws({type:`${DOMAIN}/delete_service_entry`,vehicle_id:vid,entry_index:ri});}));
    s.querySelectorAll(".del-rep").forEach(b=>b.addEventListener("click",async()=>{if(!confirm(t(h,"confirmDelete")))return;const v=this._v(),vid=this._vid();const reps=[...(v.repairs||[])].sort((a,b2)=>new Date(b2.date)-new Date(a.date));const re=reps[parseInt(b.dataset.idx)];const ri=(v.repairs||[]).findIndex(x=>x.date===re.date&&x.cat===re.cat);await this._ws({type:`${DOMAIN}/delete_repair`,vehicle_id:vid,repair_index:ri});}));
    s.querySelectorAll(".del-tire").forEach(b=>b.addEventListener("click",async()=>{if(!confirm(t(h,"confirmDelete")))return;const v=this._v(),vid=this._vid();const ti=[...(v.tires||[])].sort((a,b2)=>new Date(b2.date)-new Date(a.date));const te=ti[parseInt(b.dataset.idx)];const ri=(v.tires||[]).findIndex(x=>x.date===te.date&&x.km===te.km);await this._ws({type:`${DOMAIN}/delete_tire`,vehicle_id:vid,tire_index:ri});}));
    s.querySelectorAll(".edit-svc").forEach(b=>b.addEventListener("click",()=>{const v=this._v();const hist=[...(v.history||[])].sort((a,b2)=>new Date(b2.date)-new Date(a.date));this._showEditSvcModal(hist,parseInt(b.dataset.idx));}));
    s.getElementById("m-save-svc")?.addEventListener("click",async()=>{const vid=this._vid(),date=s.getElementById("m-date").value,km=parseInt(s.getElementById("m-km").value)||0,notes=s.getElementById("m-notes").value,services=[...s.querySelectorAll(".svc-cb:checked")].map(x=>x.value);if(!date){alert(t(h,"enterDate"));return;}if(!services.length){alert(t(h,"selectService"));return;}this._closeModal();await this._ws({type:`${DOMAIN}/add_service_entry`,vehicle_id:vid,entry_date:date,km,services,notes});});
    s.getElementById("m-save-rep")?.addEventListener("click",async()=>{const vid=this._vid(),date=s.getElementById("r-date").value,km=parseInt(s.getElementById("r-km").value)||0,category=s.getElementById("r-cat").value,description=s.getElementById("r-desc").value,cost=parseFloat(s.getElementById("r-cost").value)||0;if(!date){alert(t(h,"enterDate"));return;}this._closeModal();await this._ws({type:`${DOMAIN}/add_repair`,vehicle_id:vid,entry_date:date,km,category,description,cost});});
    s.getElementById("m-save-tire")?.addEventListener("click",async()=>{const vid=this._vid(),date=s.getElementById("t-date").value,km=parseInt(s.getElementById("t-km").value)||0,tire_type=s.getElementById("t-type").value,axle=s.getElementById("t-axle").value,width=parseInt(s.getElementById("t-w").value),ratio=parseInt(s.getElementById("t-r").value),rim=parseInt(s.getElementById("t-rim").value),brand=s.getElementById("t-brand").value,dot=s.getElementById("t-dot").value.replace(/\D/g,"").slice(0,4),vl=parseFloat(s.getElementById("t-vl").value)||0,vr=parseFloat(s.getElementById("t-vr").value)||0,hl=parseFloat(s.getElementById("t-hl").value)||0,hr=parseFloat(s.getElementById("t-hr").value)||0;if(!date){alert(t(h,"enterDate"));return;}this._closeModal();await this._ws({type:`${DOMAIN}/add_tire`,vehicle_id:vid,entry_date:date,km,tire_type,axle,width,ratio,rim,brand,dot,vl,vr,hl,hr});});
    s.getElementById("m-save-edit-svc")?.addEventListener("click",async()=>{const vid=this._vid(),v=this._v(),date=s.getElementById("m-date").value,km=parseInt(s.getElementById("m-km").value)||0,notes=s.getElementById("m-notes").value,services=[...s.querySelectorAll(".svc-cb:checked")].map(x=>x.value);if(!date||!services.length)return;const he=this._editHist[this._editIdx];const ri=(v.history||[]).findIndex(x=>x.date===he.date&&x.km===he.km&&JSON.stringify(x.services)===JSON.stringify(he.services));this._closeModal();await this._ws({type:`${DOMAIN}/update_service_entry`,vehicle_id:vid,entry_index:ri,entry_date:date,km,services,notes});});
    ["t-w","t-r","t-rim"].forEach(id=>{s.getElementById(id)?.addEventListener("change",()=>{const w=s.getElementById("t-w")?.value,r=s.getElementById("t-r")?.value,rim=s.getElementById("t-rim")?.value;const el=s.getElementById("sp");if(el)el.textContent=`\u2192 ${w}/${r} R${rim}`;});});
    s.getElementById("t-dot")?.addEventListener("input",e=>{const v=e.target.value.replace(/\D/g,"").slice(0,4);e.target.value=v;const el=s.getElementById("dp");if(el)el.textContent=v.length===4?`${t(h,"week")} ${v.slice(0,2)} / 20${v.slice(2,4)}`:"";}); }

  _css(){return`ha-card{background:var(--card-background-color,#1c1c1e);border-radius:12px}.w{padding:12px 14px 16px;font-family:var(--primary-font-family,sans-serif);color:var(--primary-text-color);position:relative}.loading{display:flex;align-items:center;gap:10px;padding:24px;color:var(--secondary-text-color);font-size:13px}.spin{width:18px;height:18px;border:2px solid var(--divider-color);border-top-color:var(--primary-color);border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0}@keyframes spin{to{transform:rotate(360deg)}}.errbox{padding:14px;background:rgba(163,45,45,.12);border:1px solid #A32D2D;border-radius:8px;font-size:12px;line-height:1.6}.empty-big,.empty{text-align:center;padding:20px;color:var(--secondary-text-color);font-size:12px;line-height:1.7}.pills{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}.pill{display:flex;align-items:center;gap:5px;padding:4px 10px;border:1px solid var(--divider-color);border-radius:20px;cursor:pointer;font-size:12px;color:var(--secondary-text-color);background:none}.pill.on{background:var(--primary-color);color:#fff;border-color:var(--primary-color)}.vhdr{display:flex;align-items:center;gap:10px;margin-bottom:12px}.vtit{font-size:16px;font-weight:500}.vmeta{display:flex;gap:5px;flex-wrap:wrap;margin-top:3px}.chip{font-size:11px;padding:1px 7px;border-radius:20px;border:1px solid var(--divider-color);color:var(--secondary-text-color)}.chip.live{background:var(--info-color,#2196F3);color:#fff;border-color:transparent}.mets{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}.met{background:var(--secondary-background-color);border-radius:8px;padding:8px 10px}.ml{font-size:11px;color:var(--secondary-text-color);margin-bottom:2px}.mv{font-size:17px;font-weight:500}.tabbar{display:flex;border-bottom:1px solid var(--divider-color);margin-bottom:12px;overflow-x:auto}.tab{padding:7px 12px;font-size:12px;font-weight:500;cursor:pointer;border:none;background:none;color:var(--secondary-text-color);border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap}.tab.on{color:var(--primary-text-color);border-bottom-color:var(--primary-color)}.srow{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--divider-color)}.srow:last-child{border-bottom:none}.sico{width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;--mdc-icon-size:20px}.sbod{flex:1;min-width:0}.snm{font-size:13px;font-weight:500}.slt{font-size:11px;color:var(--secondary-text-color);margin-top:1px}.pbar{height:4px;border-radius:2px;background:var(--divider-color);overflow:hidden;margin:4px 0 2px}.pfil{height:100%;border-radius:2px;transition:width .4s}.srt{flex-shrink:0;text-align:right;padding-left:8px}.ssub{font-size:10px;color:var(--disabled-text-color);margin-top:3px;white-space:nowrap}.badge{display:inline-flex;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:500}.shdr{display:flex;align-items:center;justify-content:space-between;font-size:13px;font-weight:500;margin-bottom:8px}.addbtn{padding:4px 10px;font-size:11px;border-radius:20px;border:1px solid var(--primary-color);color:var(--primary-color);background:none;cursor:pointer}.hrow{display:grid;grid-template-columns:110px 1fr auto;gap:10px;padding:9px 0;border-bottom:1px solid var(--divider-color)}.hrow:last-child{border-bottom:none}.hd{font-size:12px;font-weight:500}.hkm{font-size:10px;color:var(--disabled-text-color);margin-top:2px}.hn{font-size:11px;color:var(--secondary-text-color);margin-bottom:4px}.chrow{display:flex;flex-wrap:wrap}.chip2{display:inline-flex;align-items:center;gap:3px;padding:2px 6px;border-radius:20px;font-size:10px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--secondary-text-color);margin:2px}.atag{display:inline-block;font-size:10px;padding:1px 5px;border-radius:20px;background:rgba(33,150,243,.15);color:#1565C0;margin-left:4px}.rrow{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--divider-color)}.rrow:last-child{border-bottom:none}.rico{width:36px;height:36px;border-radius:8px;background:var(--info-color,#2196F3);color:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0;--mdc-icon-size:20px}.rbod{flex:1}.rnm{font-size:13px;font-weight:500}.rdsc{font-size:11px;color:var(--secondary-text-color);margin-top:1px}.rmt{font-size:10px;color:var(--disabled-text-color);margin-top:2px}.rco{font-size:12px;font-weight:500;flex-shrink:0}.ibtn{background:none;border:none;cursor:pointer;color:var(--secondary-text-color);padding:4px 6px;font-size:13px;opacity:.4;flex-shrink:0}.ibtn:hover{opacity:1;color:#A32D2D}.tcard{background:var(--secondary-background-color);border-radius:8px;padding:10px 12px;margin-bottom:8px}.tire-status-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}.tire-type-badge{display:flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:500}.tire-info-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}.ms{font-size:11px;color:var(--secondary-text-color)}.mono{font-family:monospace}.tgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.tw{background:var(--card-background-color,#1c1c1e);border-radius:8px;padding:7px 8px;border:1px solid var(--divider-color)}.twp{font-size:10px;color:var(--disabled-text-color);font-weight:600;text-transform:uppercase;margin-bottom:3px}.twv{font-size:13px;font-weight:500}.twbar{height:4px;border-radius:2px;background:var(--divider-color);overflow:hidden;margin:3px 0 2px}.twl{font-size:10px;font-weight:500}.twkm{font-size:9px;color:var(--disabled-text-color);margin-top:1px}.tnote{font-size:10px;color:var(--disabled-text-color);margin-top:8px}.overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:999;display:flex;align-items:center;justify-content:center}.mbox{background:var(--card-background-color,#1c1c1e);border-radius:12px;padding:18px;width:min(460px,92vw);max-height:88vh;overflow-y:auto;border:1px solid var(--divider-color)}.mhdr{font-size:15px;font-weight:500;display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}.closebtn{background:none;border:none;cursor:pointer;font-size:18px;color:var(--secondary-text-color);padding:0 4px}.mfld{margin-bottom:10px}.mfld label{display:block;font-size:12px;color:var(--secondary-text-color);margin-bottom:4px}.mfld input,.mfld select{width:100%;padding:7px 10px;border-radius:8px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color);font-size:13px;box-sizing:border-box}.mrow2{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}.mrow2 input,.mrow2 select{width:100%;padding:7px 10px;border-radius:8px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color);font-size:13px;box-sizing:border-box}.cbgrid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px}.cblabel{display:flex;align-items:center;gap:7px;padding:7px 10px;border:1px solid var(--divider-color);border-radius:8px;cursor:pointer;font-size:12px}.cblabel input{width:auto;margin:0}.mbtn-row{display:flex;justify-content:flex-end;margin-top:14px}.sbtn{padding:8px 20px;background:var(--primary-color);color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer}.sizerow{display:flex;align-items:center;gap:6px}.sizerow select{flex:1;padding:7px 6px;border-radius:8px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color);font-size:13px}.sep{font-size:14px;font-weight:500;color:var(--secondary-text-color);flex-shrink:0}.sizeprev,.dotprev{font-size:11px;color:var(--secondary-text-color);margin-top:4px}.profgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:6px}.profgrid select{width:100%;padding:6px 4px;border-radius:8px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color);font-size:12px}.plbl{display:block;font-size:10px;color:var(--secondary-text-color);margin-bottom:3px;font-weight:600;text-transform:uppercase}`;}
}

// ── Compact Card ───────────────────────────────────────────────────────────────
class VehicleServiceCompactCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._vehicles = [];
    this._vehicleIds = [];
    this._cur = 0;
    this._loading = true;
    this._err = null;
    this._lang = "";
  }

  setConfig(c) { this._config = c; }

  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) {
      if (h) this._load();
    } else if (h && this._vehicles.length && this._lang !== _lang(h)) {
      this._lang = _lang(h);
      this._paint();
    }
  }

  static getStubConfig() { return {}; }
  static getConfigElement() { return document.createElement("vehicle-service-compact-card-editor"); }
  getCardSize() { return 3; }

  async _load() {
    this._loading = true;
    this._paint();
    try {
      const res = await this._hass.callWS({ type: `${DOMAIN}/vehicles` });
      const entries = Object.entries(res.vehicles || {});
      this._vehicleIds = entries.map(([id]) => id);
      this._vehicles = entries.map(([, v]) => v);
      this._version = await fetchVersion(this._hass);
      this._loading = false;
    } catch (e) {
      this._err = `${e.message || e}`;
      this._loading = false;
    }
    this._paint();
  }

  _v() { return this._vehicles[this._cur]; }

  _placeholder() {
    return `
      <div style="padding:16px">
        <div style="font-size:14px;font-weight:500;margin-bottom:8px">Vehicle Service Manager</div>
        <div style="font-size:11px;color:#888;margin-bottom:10px">${t(this._hass, "subtitle")}</div>
        <div style="display:flex;gap:6px">
          ${["mdi:oil", "mdi:clipboard-check-outline", "mdi:car-brake-alert", "mdi:fan"].map((i) => `
            <div style="background:#EAF3DE;border-radius:8px;width:36px;height:36px;display:flex;align-items:center;justify-content:center">
              <ha-icon icon="${i}" style="color:#3B6D11;--mdc-icon-size:20px"></ha-icon>
            </div>`).join("")}
        </div>
      </div>`;
  }

  _paint() {
    let body = "";
    if (!this._hass) body = this._placeholder();
    else if (this._loading) body = `<div class="loading"><div class="spin"></div></div>`;
    else if (this._err) body = `<div style="padding:8px;color:#f44;font-size:11px">${t(this._hass, "errorPrefix")}${this._err}</div>`;
    else if (!this._vehicles.length) body = `<div style="padding:8px;font-size:11px;color:var(--secondary-text-color)">${t(this._hass, "noVehicles").replace(/\.$/, "")}</div>`;
    else body = this._main();

    this.shadowRoot.innerHTML = `<style>${this._css()}</style><ha-card><div class="w">${body}</div></ha-card>`;
    this.shadowRoot.querySelectorAll(".cpill").forEach((b) =>
      b.addEventListener("click", () => {
        this._cur = parseInt(b.dataset.ci, 10);
        this._paint();
      })
    );
  }

  _main() {
    const h = this._hass;
    const v = this._v();

    const pills = this._vehicles.length > 1
      ? `<div class="cpills">${this._vehicles.map((vv, i) => `<button class="cpill${i === this._cur ? " on" : ""}" data-ci="${i}">${logoHtml(vv.make || "", 14)}</button>`).join("")}</div>`
      : "";

    const icons = (v.services || []).map((sid) => {
      const r = calcPct(v, sid);
      const col = TIER_COL[r.tier];
      const bg = TIER_BG[r.tier];
      return `<div class="iico" style="background:${bg};color:${col}" title="${svcLabel(h, sid)}"><ha-icon icon="${SVC_ICONS[sid] || "mdi:wrench"}"></ha-icon></div>`;
    }).join("");

    let tireIco = "";
    const tires = v.tires || [];
    if (tires.length) {
      const lat = tires[tires.length - 1];
      const tt = lat.type || "summer";
      const wm = TIRE_WARN[tt] || 3;
      const mKm = parseInt(lat.km, 10) || 0;
      let worst = 999;

      ["vl", "vr", "hl", "hr"].forEach((pos) => {
        const orig = parseFloat(lat[pos]) || 0;
        if (orig) {
          const worn = Math.max(0, orig - Math.max(0, (v.km || 0) - mKm) * WEAR);
          if (worn < worst) worst = worn;
        }
      });

      const col = worst <= TIRE_MIN ? "#A32D2D" : worst <= wm ? "#BA7517" : "#3B6D11";
      const bg = worst <= TIRE_MIN ? "#FCEBEB" : worst <= wm ? "#FAEEDA" : "#EAF3DE";
      tireIco = `<div class="iico" style="background:${bg};color:${col}" title="${t(h, "tabTires")}"><ha-icon icon="mdi:car-tire-alert"></ha-icon></div>`;
    }

    return `${pills}<div class="chdr">${logoHtml(v.make || "", 28)}<div class="chdr-text"><div class="cvtit">${v.make || ""} ${v.model || ""}</div><div class="cvkm">${fkm(v.km, h)}</div></div></div><div class="igrid">${icons}${tireIco}</div>`;
  }

  _css() {
    return `
      ha-card { background: var(--card-background-color, #1c1c1e); border-radius: 12px; }
      .w { padding: 10px 12px 12px; font-family: var(--primary-font-family, sans-serif); color: var(--primary-text-color); }
      .loading { display: flex; align-items: center; justify-content: center; padding: 12px; }
      .spin { width: 16px; height: 16px; border: 2px solid var(--divider-color); border-top-color: var(--primary-color); border-radius: 50%; animation: spin .8s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      .cpills { display: flex; gap: 4px; margin-bottom: 8px; }
      .cpill { padding: 2px 6px; border: 1px solid var(--divider-color); border-radius: 12px; cursor: pointer; background: none; display: flex; align-items: center; gap: 3px; }
      .cpill.on { background: var(--primary-color); border-color: var(--primary-color); }
      .chdr { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
      .chdr-text { flex: 1; min-width: 0; }
      .cvtit { font-size: 13px; font-weight: 500; }
      .cvkm { font-size: 11px; color: var(--secondary-text-color); }
      .igrid { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
      .iico { width: 38px; height: 38px; border-radius: 9px; display: flex; align-items: center; justify-content: center; --mdc-icon-size: 22px; flex-shrink: 0; cursor: default; }
    `;
  }
}

// ── Editor Stubs ───────────────────────────────────────────────────────────────
// These are intentionally minimal: both cards are read-only in their config
// (all data comes from the WS API), so a no-op editor is correct. If HA complains
// about a missing editor, this stub is enough to satisfy `getConfigElement`.
class VehicleServiceCardEditor extends HTMLElement {
  constructor() { super(); }
  setConfig(c) { this._config = c; }
}
class VehicleServiceCompactCardEditor extends HTMLElement {
  constructor() { super(); }
  setConfig(c) { this._config = c; }
}

// ── Registration ──────────────────────────────────────────────────────────────
// Idempotent: safe to re-run if the resource is loaded twice (e.g. dev HMR).
if (!customElements.get("vehicle-service-card")) {
  customElements.define("vehicle-service-card", VehicleServiceCard);
}
if (!customElements.get("vehicle-service-compact-card")) {
  customElements.define("vehicle-service-compact-card", VehicleServiceCompactCard);
}
if (!customElements.get("vehicle-service-card-editor")) {
  customElements.define("vehicle-service-card-editor", VehicleServiceCardEditor);
}
if (!customElements.get("vehicle-service-compact-card-editor")) {
  customElements.define("vehicle-service-compact-card-editor", VehicleServiceCompactCardEditor);
}

// ── Card picker registration ──────────────────────────────────────────────────
// This is the ONLY thing HA's card picker needs to see the cards in the
// "Add card" list. The `type` here is the BARE tag (no `custom:` prefix);
// HA adds the prefix when rendering the card from config.
//
// `preview: true` makes the picker render a live thumbnail. Both cards already
// handle a null `hass` (they render `_placeholder()`), so the preview is safe.
// If you still don't see the cards, flip `preview` to `false` and check the
// browser console for load errors — that isolates whether it's a preview-render
// issue or a registration/timing issue.
window.customCards = window.customCards || [];
window.customCards = window.customCards.filter(
  (c) => c.type !== "vehicle-service-card" && c.type !== "vehicle-service-compact-card"
);
window.customCards.push(
  {
    type: "vehicle-service-card",
    name: "Vehicle Service Manager",
    description: "Service status, repairs and tire tracking",
    preview: true,
    documentationURL: "https://github.com/xplore93/vehicle-service-card",
  },
  {
    type: "vehicle-service-compact-card",
    name: "Vehicle Service Manager – Compact",
    description: "Service status, repairs and tire tracking (compact)",
    preview: true,
    documentationURL: "https://github.com/xplore93/vehicle-service-card",
  }
);

// Version banner is logged once by fetchVersion() when the first card loads.
