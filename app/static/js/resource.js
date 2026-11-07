'use strict';
const {resource,isAdmin}=JSON.parse(document.getElementById('pageConfig').textContent);
const def={
 'campus-users':{
   searchPlaceholder:'姓名、系所／單位、電話或 ID',
   filter:{param:'identity_type',options:[['','全部身分'],['STUDENT','學生'],['FACULTY','教師'],['STAFF','職員']]},
   key:'user_id', columns:[['user_id','ID'],['name','姓名'],['identity_type','身分'],['department','單位'],['phone','電話']],
   fields:[['name','姓名','text',true],['identity_type','身分','enum:STUDENT,FACULTY,STAFF',true],['department','系所／單位','text',true],['phone','電話','text']]},
 'vehicles':{
   searchPlaceholder:'車牌、登記人姓名或 ID',
   filter:{param:'vehicle_type',options:[['','全部車種'],['CAR','汽車'],['MOTORCYCLE','機車']]},
   key:'vehicle_id', columns:[['vehicle_id','ID'],['plate_no','車牌'],['vehicle_type','車種'],['user_name','登記人'],['permit_status','停車證狀態'],['latest_academic_year','最近學年度']],
   fields:[['plate_no','車牌','text',true],['vehicle_type','車種','enum:CAR,MOTORCYCLE',true],['user_id','登記使用者','fk:campus-users:user_id:name',true]]},
 'parking-areas':{
   searchPlaceholder:'停車區域名稱或 ID',
   filter:{param:'vehicle_type',options:[['','全部車種'],['CAR','汽車'],['MOTORCYCLE','機車']]},
   key:'area_id',columns:[['area_id','ID'],['area_name','區域名稱'],['vehicle_type','車種'],['capacity','容量'],['hourly_rate','每小時費率']],
   fields:[['area_name','區域名稱','text',true],['vehicle_type','車種','enum:CAR,MOTORCYCLE',true],['capacity','容量','number',true],['hourly_rate','每小時費率','money',true]]},
 'parking-permits':{
   searchPlaceholder:'車牌、學年度或停車證 ID',
   key:'permit_id',columns:[['permit_id','ID'],['plate_no','車牌'],['academic_year','學年'],['valid_from','生效'],['valid_to','到期'],['permit_fee','費用'],['paid_at','付款時間']],
   fields:[['vehicle_id','已登記車輛（續辦）','fk:vehicles:vehicle_id:plate_no',true],['academic_year','學年（如115）','text',true],['issue_date','核發日期','date',true],['valid_from','生效日期','date',true],['valid_to','到期日期','date',true],['permit_fee','停車證費用','money',true]]},
 'parking-records':{
   searchPlaceholder:'車牌、停車區域或紀錄 ID',
   filter:{param:'status',options:[['','全部狀態'],['OPEN','尚未離場'],['CLOSED','已離場']]},
   key:'record_id',columns:[['record_id','ID'],['plate_no','車牌'],['area_name','停車區域'],['entry_time','進場'],['exit_time','離場'],['parking_fee','停車費'],['paid_at','付款時間']],
   fields:[['plate_no','車牌（臨停不需建立車輛）','text',true],['area_id','停車區域','fk:parking-areas:area_id:area_name',true],['permit_id','使用停車證（留空自動判斷）','fk:parking-permits:permit_id:permit_id'],['entry_time','進場時間（留空使用現在）','datetime-local'],['exit_time','離場時間（留空表示尚未離場）','datetime-local']]},
 'accounts':{
   searchPlaceholder:'帳號或 ID',
   filter:{param:'role',options:[['','全部角色'],['ADMIN','管理員'],['VIEWER','檢視者']]},
   key:'account_id',columns:[['account_id','ID'],['username','帳號'],['role','角色'],['is_active','啟用'],['last_login_at','最近登入']],
   fields:[['username','登入帳號','text',true],['password','密碼（至少12字元）','password',true],['role','角色','enum:VIEWER,ADMIN',true],['is_active','啟用','boolean']]}
}[resource];
if (!def) throw new Error('未知資源');
let currentPage=1, pageCount=1, rows=[], edited=null, action=null;
let formModal, actionModal;
let searchQuery='', selectedFilter='', loadSequence=0;
const head=document.getElementById('tableHead');
const body=document.getElementById('tableBody');
const fHost=document.getElementById('formFields');
const searchInput=document.getElementById('searchInput');
const filterSelect=document.getElementById('filterSelect');
searchInput.placeholder=def.searchPlaceholder;
if (def.filter) {
  const wrap=document.getElementById('filterWrap');
  wrap.hidden=false;
  for (const [value,label] of def.filter.options) filterSelect.append(new Option(label,value));
}

function make(tag, cls, value) {
  const e=document.createElement(tag);
  if (cls) e.className=cls;
  if (value !== undefined) e.textContent=value;
  return e;
}
function fmt(v) {
  if (v===null || v===undefined || v==='') return '—';
  if (typeof v==='boolean') return v?'是':'否';
  if (typeof v==='string' && /\d{4}-\d{2}-\d{2}T/.test(v)) return new Date(v).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false});
  const permitLabels={ACTIVE:'有效',UNPAID:'未付款',UPCOMING:'尚未生效',EXPIRED:'已過期',NONE:'無停車證'};
  return permitLabels[v] || String(v);
}
async function loadRows() {
  const sequence=++loadSequence;
  const params=new URLSearchParams({page:String(currentPage),per_page:'20'});
  if (searchQuery) params.set('q',searchQuery);
  if (def.filter && selectedFilter) params.set(def.filter.param,selectedFilter);
  try {
    const result=await requestJSON(`/${resource}?${params.toString()}`);
    if (sequence!==loadSequence) return; // Ignore an older response after a new search.
    rows=result.data;pageCount=result.pagination.pages||1;
    const filtered=Boolean(searchQuery || selectedFilter);
    document.getElementById('countLabel').textContent=`${filtered?'搜尋結果：':'共 '}${result.pagination.total} 筆`;
    document.getElementById('pageInfo').textContent=`第 ${currentPage} / ${pageCount} 頁`;
    document.getElementById('prevBtn').disabled=currentPage<=1;
    document.getElementById('nextBtn').disabled=currentPage>=pageCount;
    renderTable();
  } catch(e) {
    if (sequence!==loadSequence) return;
    notify(e.message,true);
  }
}
function act(label,fn,sty='outline-primary') {
  const btn=make('button',`btn btn-sm btn-${sty} me-1 mb-1`,label);
  btn.type='button';btn.addEventListener('click',fn);return btn;
}
function renderTable() {
  head.replaceChildren();body.replaceChildren();
  for (const [,label] of def.columns) head.append(make('th','',label));
  if (isAdmin || resource==='vehicles' || resource==='campus-users') head.append(make('th','','操作'));
  if (!rows.length) { const tr=body.insertRow(),cell=tr.insertCell();cell.colSpan=def.columns.length+((isAdmin || resource==='vehicles' || resource==='campus-users')?1:0);cell.textContent=(searchQuery || selectedFilter)?'找不到符合搜尋條件的資料':'目前沒有資料';return; }
  for (const item of rows) {
    const tr=body.insertRow();
    for (const [key] of def.columns) tr.insertCell().textContent=fmt(item[key]);
    if (!isAdmin && !['vehicles','campus-users'].includes(resource)) continue;
    const buttons=tr.insertCell();
    if (resource==='campus-users') buttons.append(act('綜合查詢',()=>{window.location.href=`/people/${item.user_id}`;}));
    if (resource==='vehicles') {
      buttons.append(act('查看停車證',()=>{window.location.href=`/manage/parking-permits?q=${encodeURIComponent(item.plate_no)}`;}));
    }
    if (!isAdmin) continue;
    buttons.append(act('編輯',()=>editItem(item)));
    if (resource==='parking-permits' && !item.paid_at) buttons.append(act('付款',()=>openAction('pay-permit',item),'outline-success'));
    if (resource==='parking-records') {
      if (!item.exit_time) buttons.append(act('離場',()=>openAction('exit',item),'outline-success'));
      if (item.exit_time && item.parking_fee>0 && !item.paid_at) buttons.append(act('付款',()=>openAction('pay-record',item),'outline-success'));
    }
    if (!['accounts','vehicles'].includes(resource) && !(resource==='parking-records' && item.exit_time))
      buttons.append(act('刪除',()=>openAction('delete',item),'outline-danger'));
  }
}
async function allOptions(endpoint) {
  const out=[];
  for (let page=1; page<=20; page++) {
    const result=await requestJSON(`/${endpoint}?page=${page}&per_page=100`);
    out.push(...result.data);
    if (page >= result.pagination.pages) break;
  }
  return out;
}
async function editItem(item=null) {
  edited=item;fHost.replaceChildren();
  document.getElementById('modalTitle').textContent=item?'編輯資料':'新增資料';
  document.getElementById('formHelp').textContent=resource==='parking-records' ?
    '只需輸入車牌與停車區域；有效停車證會自動套用，來賓臨停不建立車主資料。進場中的紀錄僅可修改時間。' :
    (resource==='accounts'?'帳號只可由管理員建立；編輯時可變更角色、停用或重設密碼。':'欄位由 REST API 驗證，不會直接連線到 PostgreSQL。');
  let fields=def.fields;
  if (item && resource==='parking-records') fields=[['entry_time','進場時間','datetime-local',true]];
  if (!item && resource==='parking-permits') fields=[...fields,
    ['new_plate_no','新車車牌','text',true],
    ['new_vehicle_type','新車車種','enum:CAR,MOTORCYCLE',true],
    ['new_user_id','新車車主','fk:campus-users:user_id:name',true]];
  if (!item && resource==='accounts') fields=fields.filter(f=>f[0]!=='is_active');
  if (item && resource==='accounts') fields=[['role','角色','enum:VIEWER,ADMIN',true],['is_active','啟用','boolean'],['password','重設密碼（不更改請留空）','password']];
  if (item && resource==='parking-permits' && item.paid_at) fields=fields.filter(f=>f[0]!=='permit_fee');
  const context={};
  for (const field of fields) {
    const [key,label,type,required]=field;
    const wrap=make('div','col-sm-6');
    const lab=make('label','form-label',label);lab.htmlFor=`field_${key}`;wrap.append(lab);
    let input;
    if (type.startsWith('enum:') || type.startsWith('fk:') || type==='boolean') {
      input=make('select','form-select');
      if (!required || type.startsWith('fk:')) input.append(new Option('（未指定）',''));
      if (type==='boolean') {
        input.append(new Option('啟用','true'),new Option('停用','false'));
      } else if (type.startsWith('enum:')) {
        for (const v of type.slice(5).split(',')) input.append(new Option(v,v));
      } else {
        const [,res,idKey,labelKey]=type.split(':');
        if (!context[res]) context[res]=allOptions(res);
        const opts=await context[res];
        for (const o of opts) input.append(new Option(`${o[labelKey]} (ID ${o[idKey]})`,o[idKey]));
      }
    } else {
      input=make('input','form-control');
      input.type=(type==='money'||type==='number')?'number':type;
      if (type==='money') {input.step='.01';input.min='0';}
      if (type==='number') input.min='1';
      if (key==='plate_no') input.maxLength=20;
    }
    input.id=`field_${key}`;input.name=key;input.required=Boolean(required);
    let original=item?.[key];
    if (original !== null && original !== undefined) {
      if (type==='datetime-local' && original) {
        const d=new Date(original);const local=new Date(d.getTime()+8*3600000);
        original=local.toISOString().slice(0,16);
      }
      input.value=String(original);
    }
    wrap.append(input);fHost.append(wrap);
  }
  if (!item && resource==='parking-permits') {
    const wrap=make('div','col-12');
    const modeLabel=make('label','form-label','辦理方式');modeLabel.htmlFor='permitVehicleMode';
    const mode=make('select','form-select');mode.id='permitVehicleMode';
    mode.append(new Option('新車首次辦證','new'),new Option('既有車輛續辦','existing'));
    wrap.append(modeLabel,mode);
    fHost.prepend(wrap);
    const sync=()=>{
      const isNew=mode.value==='new';
      for (const name of ['vehicle_id','new_plate_no','new_vehicle_type','new_user_id']) {
        const input=document.getElementById(`field_${name}`);
        if (!input) continue;
        const show=(name==='vehicle_id')?!isNew:isNew;
        input.parentElement.hidden=!show;
        input.required=show;
      }
    };
    mode.addEventListener('change',sync);
    sync();
  }
  formModal.show();
}
document.getElementById('editForm').addEventListener('submit',async(e)=>{
  e.preventDefault();
  const data={};
  for (const input of fHost.querySelectorAll('[name]')) {
    if (input.parentElement.hidden) continue;
    if (!input.value && (input.name==='password' && edited || !input.required)) {
      if (input.name==='user_id' || input.name==='permit_id') data[input.name]=null;
      continue;
    }
    if (input.name==='is_active') data[input.name]=input.value==='true';
    else if (['capacity','vehicle_id','user_id','new_user_id','area_id','permit_id'].includes(input.name)) data[input.name]=input.value?Number(input.value):null;
    else if (input.type==='datetime-local') data[input.name]=input.value?`${input.value}:00+08:00`:null;
    else data[input.name]=input.value;
  }
  if (!edited && resource==='parking-permits') {
    if (document.getElementById('permitVehicleMode').value==='new') {
      data.new_vehicle={plate_no:data.new_plate_no,vehicle_type:data.new_vehicle_type,user_id:data.new_user_id};
      delete data.vehicle_id;
    }
    delete data.new_plate_no;delete data.new_vehicle_type;delete data.new_user_id;
  }
  try {
    const endpoint=edited?`/${resource}/${edited[def.key]}`:`/${resource}`;
    await requestJSON(endpoint,{method:edited?'PATCH':'POST',body:data});
    formModal.hide();notify('資料已儲存');await loadRows();
  } catch(ex) {notify(ex.message,true);}
});
function openAction(kind,item) {
  action={kind,item};
  document.getElementById('actionTitle').textContent={'delete':'確認刪除','exit':'登記離場','pay-permit':'停車證付款','pay-record':'停車費付款'}[kind];
  document.getElementById('actionMessage').textContent=kind==='delete'?'確定刪除此筆資料？已有關聯資料者不得刪除。':`資料編號：${item[def.key]}`;
  const host=document.getElementById('actionField');host.replaceChildren();
  if (kind.startsWith('pay-')) {
    const select=make('select','form-select mt-3');select.id='payMethod';
    for (const [key,text] of [['CASH','現金'],['CARD','信用卡'],['TRANSFER','轉帳']]) select.append(new Option(text,key));
    host.append(make('label','form-label mt-3','付款方式'),select);
  }
  actionModal.show();
}
document.getElementById('actionForm').addEventListener('submit',async e=>{
  e.preventDefault();if (!action) return;
  const {kind,item}=action;
  let path=`/${resource}/${item[def.key]}`,method='POST',body={};
  if (kind==='delete') method='DELETE';
  if (kind==='exit') path+='/exit';
  if (kind==='pay-permit'||kind==='pay-record') {
    path+='/pay';body.payment_method=document.getElementById('payMethod').value;
  }
  try { await requestJSON(path,{method,body});actionModal.hide();notify('操作成功');loadRows(); }
  catch(ex) {notify(ex.message,true);}
});
function applySearch() {
  searchQuery=searchInput.value.trim();
  selectedFilter=def.filter?filterSelect.value:'';
  currentPage=1;
  loadRows();
}
document.getElementById('searchForm').addEventListener('submit',e=>{
  e.preventDefault();
  applySearch();
});
if (def.filter) filterSelect.addEventListener('change',applySearch);
document.getElementById('clearSearchBtn').addEventListener('click',()=>{
  searchInput.value='';
  if (def.filter) filterSelect.value='';
  applySearch();
  searchInput.focus();
});
document.getElementById('refreshBtn').addEventListener('click',loadRows);
document.getElementById('prevBtn').addEventListener('click',()=>{currentPage--;loadRows();});
document.getElementById('nextBtn').addEventListener('click',()=>{currentPage++;loadRows();});
const newBtn=document.getElementById('newBtn');
if (newBtn) {
  if (resource==='vehicles') {
    newBtn.textContent='＋ 辦理停車證';
    newBtn.addEventListener('click',()=>{window.location.href='/manage/parking-permits?new=1';});
  } else newBtn.addEventListener('click',()=>editItem().catch(e=>notify(e.message,true)));
}
formModal=new bootstrap.Modal(document.getElementById('editModal'));
actionModal=new bootstrap.Modal(document.getElementById('actionModal'));
const urlParams=new URLSearchParams(window.location.search);
if (urlParams.get('q')) {searchInput.value=urlParams.get('q');searchQuery=searchInput.value.trim();}
loadRows();
if (resource==='parking-permits' && urlParams.get('new')==='1' && isAdmin) {
  editItem().catch(e=>notify(e.message,true));
}
