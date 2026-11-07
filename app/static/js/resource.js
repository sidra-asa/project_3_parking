'use strict';

const {resource, isAdmin} = JSON.parse(document.getElementById('pageConfig').textContent);
const definitions = {
  'campus-users': {
    searchPlaceholder:'姓名、系所／單位、電話或人員編號',
    filter:{param:'identity_type',options:[['','全部身分'],['STUDENT','學生'],['FACULTY','教師'],['STAFF','職員']]},
    key:'user_id',
    columns:[['name','姓名'],['identity_type','身分'],['department','單位'],['phone','電話'],['user_id','編號']],
    fields:[['name','姓名','text',true],['identity_type','身分','enum:STUDENT,FACULTY,STAFF',true],['department','系所／單位','text',true],['phone','電話','text']]
  },
  'vehicles': {
    searchPlaceholder:'車牌、登記人姓名或車輛編號',
    filter:{param:'vehicle_type',options:[['','全部車種'],['CAR','汽車'],['MOTORCYCLE','機車']]},
    key:'vehicle_id',
    columns:[['plate_no','車牌'],['vehicle_type','車種'],['user_name','登記人'],['permit_status','停車證狀態'],['latest_academic_year','最近學年度'],['vehicle_id','編號']],
    fields:[['plate_no','車牌','text',true],['vehicle_type','車種','enum:CAR,MOTORCYCLE',true],['user_id','登記使用者','fk:campus-users:user_id:name',true]]
  },
  'parking-areas': {
    searchPlaceholder:'停車區名稱或區域編號',
    filter:{param:'vehicle_type',options:[['','全部車種'],['CAR','汽車'],['MOTORCYCLE','機車']]},
    key:'area_id',
    columns:[['area_name','停車區域'],['vehicle_type','車種'],['capacity','車位容量'],['hourly_rate','每小時費率'],['area_id','編號']],
    fields:[['area_name','區域名稱','text',true],['vehicle_type','車種','enum:CAR,MOTORCYCLE',true],['capacity','容量','number',true],['hourly_rate','每小時費率','money',true]]
  },
  'parking-permits': {
    searchPlaceholder:'車牌、學年度或停車證編號',
    key:'permit_id',
    columns:[['plate_no','車牌'],['academic_year','學年度'],['valid_from','生效日期'],['valid_to','到期日期'],['permit_fee','費用'],['paid_at','付款時間'],['permit_id','編號']],
    fields:[['vehicle_id','已登記車輛（續辦）','fk:vehicles:vehicle_id:plate_no',true],['academic_year','學年（如 115）','text',true],['issue_date','核發日期','date',true],['valid_from','生效日期','date',true],['valid_to','到期日期','date',true],['permit_fee','停車證費用','money',true]]
  },
  'parking-records': {
    searchPlaceholder:'車牌、停車區名稱或紀錄編號',
    filter:{param:'status',options:[['','全部狀態'],['OPEN','尚未離場'],['CLOSED','已離場']]},
    key:'record_id',
    columns:[['plate_no','車牌'],['area_name','停車區域'],['entry_time','進場'],['exit_time','離場'],['parking_fee','停車費'],['paid_at','付款時間'],['record_id','編號']],
    fields:[['plate_no','車牌（臨停不需登記車主）','text',true],['area_id','停車區域','fk:parking-areas:area_id:area_name',true],['permit_id','套用停車證（留空自動判斷）','fk:parking-permits:permit_id:permit_id'],['entry_time','進場時間（留空使用現在）','datetime-local'],['exit_time','離場時間','datetime-local']]
  },
  'accounts': {
    searchPlaceholder:'登入帳號或帳號編號',
    filter:{param:'role',options:[['','全部角色'],['ADMIN','管理員'],['VIEWER','檢視者']]},
    key:'account_id',
    columns:[['username','登入帳號'],['role','角色'],['is_active','啟用狀態'],['last_login_at','最近登入'],['account_id','編號']],
    fields:[['username','登入帳號','text',true],['password','密碼（至少 12 字元）','password',true],['role','角色','enum:VIEWER,ADMIN',true],['is_active','啟用','boolean']]
  }
};
const def = definitions[resource];
if (!def) throw new Error('不支援的管理頁面');

let currentPage=1, pageCount=1, rows=[], edited=null, action=null;
let searchQuery='', selectedFilter='', loadSequence=0;
const head=document.getElementById('tableHead');
const body=document.getElementById('tableBody');
const fieldsHost=document.getElementById('formFields');
const searchInput=document.getElementById('searchInput');
const filterSelect=document.getElementById('filterSelect');
const formModal=new bootstrap.Modal(document.getElementById('editModal'));
const actionModal=new bootstrap.Modal(document.getElementById('actionModal'));
const newBtn=document.getElementById('newBtn');

searchInput.placeholder=def.searchPlaceholder;
if (def.filter) {
  document.getElementById('filterWrap').hidden=false;
  for (const [value,label] of def.filter.options) filterSelect.append(new Option(label,value));
}

function element(tag,cls,text) {
  const node=document.createElement(tag);
  if (cls) node.className=cls;
  if (text!==undefined) node.textContent=text;
  return node;
}
function display(value) {
  if (value===null || value===undefined || value==='') return '—';
  if (typeof value==='boolean') return value?'是':'否';
  if (typeof value==='string' && /^\d{4}-\d{2}-\d{2}T/.test(value))
    return new Date(value).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false});
  const labels={CAR:'汽車',MOTORCYCLE:'機車',STUDENT:'學生',FACULTY:'教師',STAFF:'行政人員',
    ADMIN:'管理員',VIEWER:'檢視者',ACTIVE:'有效',UNPAID:'未付款',UPCOMING:'尚未生效',EXPIRED:'已過期',NONE:'無停車證'};
  return labels[value] || String(value);
}
function actionButton(label,callback,style='outline-primary') {
  const btn=element('button',`btn btn-sm btn-${style} me-1 mb-1`,label);
  btn.type='button'; btn.addEventListener('click',callback); return btn;
}
function primaryLabel(item) {
  const names={'campus-users':item.name,'vehicles':item.plate_no,'parking-areas':item.area_name,
    'parking-permits':`${item.plate_no}（${item.academic_year} 學年度）`,
    'parking-records':`${item.plate_no}（${item.area_name}）`,'accounts':item.username};
  return names[resource] || `編號 ${item[def.key]}`;
}

async function loadRows() {
  const sequence=++loadSequence;
  const params=new URLSearchParams({page:String(currentPage),per_page:'20'});
  if (searchQuery) params.set('q',searchQuery);
  if (def.filter && selectedFilter) params.set(def.filter.param,selectedFilter);
  try {
    const result=await requestJSON(`/${resource}?${params.toString()}`);
    if (sequence!==loadSequence) return;
    rows=result.data;
    pageCount=result.pagination.pages || 1;
    document.getElementById('countLabel').textContent=`${searchQuery||selectedFilter?'搜尋結果：':'共 '}${result.pagination.total} 筆`;
    document.getElementById('pageInfo').textContent=`第 ${currentPage} / ${pageCount} 頁`;
    document.getElementById('prevBtn').disabled=currentPage<=1;
    document.getElementById('nextBtn').disabled=currentPage>=pageCount;
    renderTable();
  } catch(e) {
    if (sequence===loadSequence) notify(e.message,true);
  }
}
function renderTable() {
  head.replaceChildren(); body.replaceChildren();
  for (const [key,label] of def.columns) {
    const cell=element('th',key===def.key?'column-id':'',label);
    cell.scope='col'; head.append(cell);
  }
  const showActions=isAdmin || ['vehicles','campus-users'].includes(resource);
  if (showActions) { const cell=element('th','','操作');cell.scope='col';head.append(cell); }
  if (!rows.length) {
    const row=body.insertRow(),cell=row.insertCell();
    cell.colSpan=def.columns.length+(showActions?1:0);
    cell.textContent=searchQuery||selectedFilter?'找不到符合條件的資料':'目前沒有資料';
    return;
  }
  for (const item of rows) {
    const tr=body.insertRow();
    for (const [key] of def.columns) {
      const cell=tr.insertCell();cell.textContent=display(item[key]);
      if (key===def.key) cell.className='column-id';
    }
    if (!showActions) continue;
    const buttons=tr.insertCell();
    if (resource==='campus-users') buttons.append(actionButton('查看詳細資料',()=>{window.location.href=`/people/${item.user_id}`;}));
    if (resource==='vehicles') buttons.append(actionButton('查看停車證',()=>{window.location.href=`/manage/parking-permits?q=${encodeURIComponent(item.plate_no)}`;}));
    if (!isAdmin) continue;
    // Historical, already-exited parking records are read-only.
    if (!(resource==='parking-records' && item.exit_time)) buttons.append(actionButton('編輯',()=>editItem(item).catch(e=>notify(e.message,true))));
    if (resource==='parking-permits' && !item.paid_at) buttons.append(actionButton('登記付款',()=>openAction('pay-permit',item),'outline-success'));
    if (resource==='parking-records') {
      if (!item.exit_time) buttons.append(actionButton('辦理離場',()=>openAction('exit',item),'outline-success'));
      if (item.exit_time && item.parking_fee>0 && !item.paid_at) buttons.append(actionButton('收取停車費',()=>openAction('pay-record',item),'outline-success'));
    }
    if (!['accounts','vehicles'].includes(resource) && !(resource==='parking-records' && item.exit_time))
      buttons.append(actionButton('刪除',()=>openAction('delete',item),'outline-danger'));
  }
}

// Search related people and vehicles on demand rather than loading only the first 2,000 records.
async function createForeignKeyField(wrap,key,resourceName,idKey,labelKey,selectedValue,required) {
  const select=element('select','form-select');
  select.id=`field_${key}`;select.name=key;select.required=Boolean(required);
  const search=element('input','form-control form-control-sm mt-2');
  search.type='search';search.autocomplete='off';search.placeholder='輸入關鍵字篩選選項';
  search.setAttribute('aria-label',`搜尋${labelKey==='name'?'人員':labelKey==='plate_no'?'車輛':'相關資料'}`);
  let lastSearch=0, debounce=null;
  const update=async (q='')=>{
    const seq=++lastSearch;
    const params=new URLSearchParams({page:'1',per_page:'50'});
    if (q) params.set('q',q);
    const result=await requestJSON(`/${resourceName}?${params.toString()}`);
    if (seq!==lastSearch) return;
    const current=select.value || String(selectedValue??'');
    select.replaceChildren(new Option(required?'請選擇':'（不指定）',''));
    let matched=false;
    for (const item of result.data) {
      const value=String(item[idKey]);
      select.append(new Option(`${item[labelKey]}（編號 ${value}）`,value));
      if (current===value) matched=true;
    }
    if (current && !matched) select.append(new Option(`目前選取的資料（編號 ${current}）`,current));
    if (current) select.value=current;
  };
  search.addEventListener('input',()=>{
    clearTimeout(debounce);
    debounce=setTimeout(()=>update(search.value.trim()).catch(e=>notify(e.message,true)),300);
  });
  wrap.append(select,search);
  await update();
  return select;
}

function formGuidance(item) {
  if (resource==='parking-records') return item
    ? '進場中的紀錄可調整進場時間；辦理離場及付款請使用列表上的按鈕。'
    : '輸入車牌和停車區即可登記進場。系統會自動判斷是否有可用的已付款停車證，臨停不必先建立車主資料。';
  if (resource==='parking-permits') return item
    ? '請確認學年度、有效期間及費用；已付款的停車證不能變更原收費金額。'
    : '首次申辦會一併登記新車，續辦則選擇已登記車輛。同一車輛同一學年度只能辦理一次。';
  if (resource==='vehicles') return '此頁僅可修改已登記車輛；新增車輛請先辦理首次學年度停車證。';
  if (resource==='accounts') return '只有管理員能建立及調整帳號。編輯時若不需變更密碼，請保持空白。';
  return '請確認資料正確後再儲存。';
}
async function editItem(item=null,preferredMode='new') {
  edited=item;
  fieldsHost.replaceChildren();
  const newLabels={'campus-users':'新增校內使用者','vehicles':'編輯登記車輛','parking-areas':'新增停車區域',
    'parking-permits':preferredMode==='existing'?'既有車輛續辦':'首次申辦停車證',
    'parking-records':'登記車輛進場','accounts':'新增網站帳號'};
  document.getElementById('modalTitle').textContent=item?`編輯${primaryLabel(item)}`:newLabels[resource];
  document.getElementById('formHelp').textContent=formGuidance(item);
  document.getElementById('saveBtn').textContent=item?'儲存修改':resource==='parking-records'?'確認進場':resource==='parking-permits'?'確認申辦':'確認新增';
  let fields=def.fields;
  if (item && resource==='parking-records') fields=[['entry_time','進場時間','datetime-local',true]];
  if (!item && resource==='parking-records') fields=fields.filter(f=>!['exit_time','permit_id'].includes(f[0]));
  if (!item && resource==='parking-permits') fields=[...fields,
    ['new_plate_no','新車車牌','text',true],
    ['new_vehicle_type','新車車種','enum:CAR,MOTORCYCLE',true],
    ['new_user_id','新車車主','fk:campus-users:user_id:name',true]];
  if (!item && resource==='accounts') fields=fields.filter(f=>f[0]!=='is_active');
  if (item && resource==='accounts') fields=[['role','角色','enum:VIEWER,ADMIN',true],['is_active','啟用','boolean'],['password','重設密碼（不更改請留空）','password']];
  if (item && resource==='parking-permits' && item.paid_at) fields=fields.filter(f=>f[0]!=='permit_fee');
  for (const [key,label,type,required] of fields) {
    const wrap=element('div','col-sm-6');
    const lab=element('label','form-label',label);lab.htmlFor=`field_${key}`;wrap.append(lab);
    const original=item?.[key];
    let input;
    if (type.startsWith('fk:')) {
      const [,related,idKey,labelKey]=type.split(':');
      input=await createForeignKeyField(wrap,key,related,idKey,labelKey,original,required);
    } else if (type.startsWith('enum:') || type==='boolean') {
      input=element('select','form-select');
      if (!required) input.append(new Option('（不指定）',''));
      if (type==='boolean') {
        input.append(new Option('啟用','true'),new Option('停用','false'));
      } else {
        for (const value of type.slice(5).split(',')) input.append(new Option(display(value),value));
      }
    } else {
      input=element('input','form-control');
      input.type=type==='money'||type==='number'?'number':type;
      if (type==='money') {input.step='.01';input.min='0';}
      if (type==='number') input.min='1';
      if (key==='plate_no' || key==='new_plate_no') input.maxLength=20;
    }
    input.id=`field_${key}`;input.name=key;input.required=Boolean(required);
    if (original !== null && original !== undefined) {
      let value=original;
      if (type==='datetime-local' && original) value=new Date(new Date(original).getTime()+8*3600000).toISOString().slice(0,16);
      input.value=String(value);
    }
    if (!type.startsWith('fk:')) wrap.append(input);
    fieldsHost.append(wrap);
  }
  if (!item && resource==='parking-permits') {
    const wrap=element('div','col-12');
    const lab=element('label','form-label','辦理方式');lab.htmlFor='permitVehicleMode';
    const mode=element('select','form-select');mode.id='permitVehicleMode';
    mode.append(new Option('新車首次申辦','new'),new Option('既有車輛續辦','existing'));
    mode.value=preferredMode;
    wrap.append(lab,mode);fieldsHost.prepend(wrap);
    const sync=()=>{
      const isNew=mode.value==='new';
      document.getElementById('modalTitle').textContent=isNew?'首次申辦停車證':'既有車輛續辦';
      for (const name of ['vehicle_id','new_plate_no','new_vehicle_type','new_user_id']) {
        const input=document.getElementById(`field_${name}`);
        if (!input) continue;
        const show=name==='vehicle_id'?!isNew:isNew;
        input.parentElement.hidden=!show;
        input.required=show;
      }
    };
    mode.addEventListener('change',sync); sync();
  }
  formModal.show();
}

document.getElementById('editForm').addEventListener('submit',async event=>{
  event.preventDefault();
  const payload={};
  for (const input of fieldsHost.querySelectorAll('[name]')) {
    if (input.parentElement.hidden) continue;
    if (!input.value && ((input.name==='password' && edited) || !input.required)) {
      if (input.name==='user_id' || input.name==='permit_id') payload[input.name]=null;
      continue;
    }
    if (input.name==='is_active') payload[input.name]=input.value==='true';
    else if (['capacity','vehicle_id','user_id','new_user_id','area_id','permit_id'].includes(input.name)) payload[input.name]=input.value?Number(input.value):null;
    else if (input.type==='datetime-local') payload[input.name]=input.value?`${input.value}:00+08:00`:null;
    else payload[input.name]=input.value;
  }
  if (!edited && resource==='parking-permits') {
    if (document.getElementById('permitVehicleMode').value==='new') {
      payload.new_vehicle={plate_no:payload.new_plate_no,vehicle_type:payload.new_vehicle_type,user_id:payload.new_user_id};
      delete payload.vehicle_id;
    }
    delete payload.new_plate_no;delete payload.new_vehicle_type;delete payload.new_user_id;
  }
  try {
    const path=edited?`/${resource}/${edited[def.key]}`:`/${resource}`;
    await requestJSON(path,{method:edited?'PATCH':'POST',body:payload});
    formModal.hide();notify(edited?'修改已儲存':'新增完成');await loadRows();
  } catch(e) {notify(e.message,true);}
});

function openAction(kind,item) {
  action={kind,item};
  document.getElementById('actionTitle').textContent={delete:'確認刪除',exit:'辦理車輛離場','pay-permit':'登記停車證付款','pay-record':'收取停車費'}[kind];
  document.getElementById('actionMessage').textContent=kind==='delete'
    ? `確定要刪除「${primaryLabel(item)}」嗎？已有關聯紀錄時可能無法刪除。`
    : `處理項目：${primaryLabel(item)}`;
  const host=document.getElementById('actionField');host.replaceChildren();
  if (kind.startsWith('pay-')) {
    const label=element('label','form-label mt-3','付款方式');label.htmlFor='payMethod';
    const select=element('select','form-select');select.id='payMethod';
    for (const [value,text] of [['CASH','現金'],['CARD','信用卡'],['TRANSFER','轉帳']]) select.append(new Option(text,value));
    host.append(label,select);
  }
  actionModal.show();
}
document.getElementById('actionForm').addEventListener('submit',async event=>{
  event.preventDefault();if (!action) return;
  const {kind,item}=action;
  let path=`/${resource}/${item[def.key]}`,method='POST',payload={};
  if (kind==='delete') method='DELETE';
  if (kind==='exit') path+='/exit';
  if (kind==='pay-permit' || kind==='pay-record') {
    path+='/pay'; payload.payment_method=document.getElementById('payMethod').value;
  }
  try {
    await requestJSON(path,{method,body:payload});
    actionModal.hide();notify('操作已完成');await loadRows();
  } catch(e) {notify(e.message,true);}
});

function applySearch() {
  searchQuery=searchInput.value.trim();
  selectedFilter=def.filter?filterSelect.value:'';
  currentPage=1;loadRows();
}
document.getElementById('searchForm').addEventListener('submit',e=>{e.preventDefault();applySearch();});
if (def.filter) filterSelect.addEventListener('change',applySearch);
document.getElementById('clearSearchBtn').addEventListener('click',()=>{
  searchInput.value='';if (def.filter) filterSelect.value='';applySearch();searchInput.focus();
});
document.getElementById('refreshBtn').addEventListener('click',loadRows);
document.getElementById('prevBtn').addEventListener('click',()=>{if(currentPage>1){currentPage--;loadRows();}});
document.getElementById('nextBtn').addEventListener('click',()=>{if(currentPage<pageCount){currentPage++;loadRows();}});
if (newBtn) {
  const labels={'campus-users':'＋ 新增校內使用者','vehicles':'＋ 首次申辦停車證','parking-areas':'＋ 新增停車區域',
    'parking-permits':'＋ 新車首次申辦','parking-records':'＋ 車輛進場','accounts':'＋ 新增網站帳號'};
  newBtn.textContent=labels[resource];
  if (resource==='vehicles') newBtn.addEventListener('click',()=>{window.location.href='/manage/parking-permits?new=1&mode=new';});
  else newBtn.addEventListener('click',()=>editItem().catch(e=>notify(e.message,true)));
}
const renewBtn=document.getElementById('renewBtn');
if (renewBtn) renewBtn.addEventListener('click',()=>editItem(null,'existing').catch(e=>notify(e.message,true)));
const queryParams=new URLSearchParams(window.location.search);
if (queryParams.get('q')) {searchInput.value=queryParams.get('q');searchQuery=searchInput.value.trim();}
loadRows();
if (resource==='parking-permits' && queryParams.get('new')==='1' && isAdmin) {
  const mode=queryParams.get('mode')==='existing'?'existing':'new';
  editItem(null,mode).catch(e=>notify(e.message,true));
}
