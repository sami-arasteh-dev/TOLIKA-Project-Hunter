import os,json,sqlite3,datetime,re,csv,io
from pathlib import Path
from flask import Flask,render_template,request,jsonify,send_file
from openai import OpenAI
BASE=Path(__file__).resolve().parent; DB=BASE/'tolika_sales.sqlite3'; EXP=BASE/'exports'; EXP.mkdir(exist_ok=True)
app=Flask(__name__); app.config['MAX_CONTENT_LENGTH']=25*1024*1024

def now(): return datetime.datetime.now().isoformat(timespec='seconds')
def con():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def allq(q,a=()):
 c=con(); r=[dict(x) for x in c.execute(q,a).fetchall()]; c.close(); return r
def one(q,a=()):
 c=con(); r=c.execute(q,a).fetchone(); c.close(); return dict(r) if r else None
def exe(q,a=()):
 c=con(); x=c.execute(q,a); c.commit(); lid=x.lastrowid; c.close(); return lid

def init():
 c=con(); c.executescript('''
 CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),base_url TEXT DEFAULT 'https://api.gapgpt.app/v1',api_key TEXT DEFAULT '',model TEXT DEFAULT 'gpt-4o',temperature REAL DEFAULT .2,max_tokens INTEGER DEFAULT 6000,system_prompt TEXT DEFAULT '',web_enabled INTEGER DEFAULT 1,updated_at TEXT);
 CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE,name TEXT NOT NULL,city TEXT,address TEXT,project_type TEXT,stage TEXT DEFAULT 'Lead',source TEXT,owner TEXT DEFAULT 'سامان',client TEXT,investor TEXT,pm_company TEXT,manager TEXT,contract_contact TEXT,procurement_contact TEXT,architect TEXT,interior_designer TEXT,contractor TEXT,phone TEXT,mobile TEXT,email TEXT,website TEXT,wood_opportunity INTEGER DEFAULT 0,metal_opportunity INTEGER DEFAULT 0,cnc_opportunity INTEGER DEFAULT 0,doors_opportunity INTEGER DEFAULT 0,wall_opportunity INTEGER DEFAULT 0,fixed_furniture_opportunity INTEGER DEFAULT 0,counter_opportunity INTEGER DEFAULT 0,other_opportunity TEXT,contract_status TEXT DEFAULT 'نامشخص',estimated_value REAL DEFAULT 0,budget REAL DEFAULT 0,payment_terms TEXT,deadline TEXT,notes TEXT,score REAL DEFAULT 0,last_contact TEXT,next_action TEXT,next_action_date TEXT,created_at TEXT,updated_at TEXT);
 CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id INTEGER,name TEXT NOT NULL,role TEXT,company TEXT,phone TEXT,mobile TEXT,email TEXT,channel TEXT,influence INTEGER DEFAULT 50,decision_power INTEGER DEFAULT 50,notes TEXT,last_contact TEXT,next_action TEXT,next_action_date TEXT,FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
 CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id INTEGER,contact_id INTEGER,kind TEXT,result TEXT,notes TEXT,occurred_at TEXT,next_action TEXT,next_action_date TEXT,FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
 CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id INTEGER,title TEXT NOT NULL,due_date TEXT,priority TEXT DEFAULT 'Medium',status TEXT DEFAULT 'Open',notes TEXT,created_at TEXT,FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
 CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,project_id INTEGER,payload TEXT,created_at TEXT,FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL);
 CREATE TABLE IF NOT EXISTS saved_recommendations(id INTEGER PRIMARY KEY AUTOINCREMENT,analysis_id INTEGER,title TEXT,payload TEXT,created_at TEXT,FOREIGN KEY(analysis_id) REFERENCES analyses(id) ON DELETE CASCADE);
 ''')
 if not c.execute('SELECT 1 FROM settings WHERE id=1').fetchone(): c.execute('INSERT INTO settings(id,updated_at) VALUES(1,?)',(now(),))
 c.commit(); c.close()

def score(p):
 def pct(v): return max(0,min(100,float(v or 0)))
 wood=pct(p.get('wood_opportunity')); metal=pct(p.get('metal_opportunity')); access=100 if p.get('manager') or p.get('contract_contact') or p.get('procurement_contact') else 20
 contract={'واگذار نشده':100,'در حال مذاکره':80,'نامشخص':50,'پیمانکار مشخص شده':25,'قرارداد شده':0}.get(p.get('contract_status'),50)
 stage={'Lead':60,'Opportunity':85,'Meeting':80,'Scope':95,'Proposal':100,'Negotiation':100,'Contract':0}.get(p.get('stage'),60)
 budget=100 if float(p.get('budget') or 0)>=5e9 else 70 if float(p.get('budget') or 0)>=1e9 else 40
 fit=wood*.5+metal*.25+pct(p.get('cnc_opportunity'))*.1+pct(p.get('fixed_furniture_opportunity'))*.15
 return round(.20*100+.15*wood+.10*metal+.15*contract+.15*access+.10*stage+.10*budget+.05*min(100,fit),1)

def clean_ai(d,target=None):
 if not isinstance(d,dict): d={}
 def arr(k): return d[k] if isinstance(d.get(k),list) else []
 nodes,edges=arr('nodes'),arr('edges')
 if target and not nodes:
  nodes=[{'id':'tolika','label':'تولیکا','type':'محور','description':'مجموعه محور'},{'id':'project','label':target['name'],'type':'پروژه','description':'فرصت بالقوه'}]
  edges=[{'source':'tolika','target':'project','weight':75,'relationship':'فرصت فروش','reason':'ثبت فرصت پروژه','conditions':'تأیید Scope','offer':'جلسه و برآورد اولیه','timing':'فوری','confidence':50}]
 return {'summary':str(d.get('summary','تحلیل انجام شد.')),'network_strategy':str(d.get('network_strategy','')),'assumptions':arr('assumptions'),'external_signals':arr('external_signals'),'nodes':nodes,'edges':edges,'recommendations':arr('recommendations'),'campaigns':arr('campaigns'),'priority_actions':arr('priority_actions'),'risks':arr('risks')}

def analyze(pid,context):
 s=one('SELECT * FROM settings WHERE id=1')
 if not s['api_key']: raise RuntimeError('API Key در تنظیمات وارد نشده است.')
 ps=allq('SELECT * FROM projects ORDER BY score DESC,updated_at DESC'); cs=allq('SELECT c.*,p.name project_name FROM contacts c LEFT JOIN projects p ON p.id=c.project_id ORDER BY decision_power DESC,influence DESC'); target=one('SELECT * FROM projects WHERE id=?',(pid,)) if pid else None
 prompt=f'''تو موتور Enterprise «شکار پروژه و هم‌افزایی تجاری تولیکا» هستی. هدف، تبدیل پروژه‌های ساختمانی، هتلی و تجاری به قرارداد دکوراسیون داخلی، چوب، MDF، CNC، درب، دیوارپوش، مبلمان ثابت، کانتر و فلز است. داده‌ها: {json.dumps(ps,ensure_ascii=False)} افراد: {json.dumps(cs,ensure_ascii=False)} هدف: {json.dumps(target,ensure_ascii=False) if target else 'کل Pipeline'} زمینه کاربر: {context}\nاگر ابزار وب واقعی در Gateway در دسترس است، سیگنال تازه جمع کن؛ در غیر این صورت هیچ داده بیرونی را واقعیت قطعی ندان و در external_signals برچسب «نیازمند راستی‌آزمایی» بزن. فقط JSON معتبر بده با کلیدهای summary,network_strategy,assumptions,external_signals,nodes,edges,recommendations,campaigns,priority_actions,risks. nodes=[{{id,label,type,description}}]. edges=[{{source,target,weight,relationship,reason,conditions,offer,timing,confidence}}]. weight/confidence بین 0 و100. recommendations=[{{title,priority,target,action,reason,offer,expected_value,timing,confidence,kpi}}]. campaigns=[{{title,goal,steps,duration_days,budget,success_metric}}]. priority_actions=[{{action,project,owner,due,priority}}]. risks=[{{risk,impact,mitigation}}]. پیشنهادها عملی و قابل پیگیری باشند، نه کلی. روابط را فقط وقتی داده یا منطق کافی داری با اطمینان بالا وزن نده.'''
 if s['system_prompt']: prompt=s['system_prompt']+'\n'+prompt
 client=OpenAI(base_url=s['base_url'],api_key=s['api_key']); r=client.chat.completions.create(model=s['model'],temperature=float(s['temperature']),max_tokens=int(s['max_tokens']),messages=[{'role':'system','content':'Return valid JSON only.'},{'role':'user','content':prompt}])
 text=(r.choices[0].message.content or '{}').strip(); text=re.sub(r'^```json\s*|\s*```$','',text,flags=re.I)
 try:d=json.loads(text)
 except: 
  m=re.search(r'\{.*\}',text,re.S)
  if not m: raise RuntimeError('مدل خروجی JSON معتبر برنگرداند.')
  d=json.loads(m.group())
 return clean_ai(d,target)

@app.route('/')
def home(): return render_template('index.html')
@app.get('/api/projects')
def projects():
 p=allq('SELECT * FROM projects ORDER BY updated_at DESC');
 for x in p:x['score']=score(x)
 return jsonify(p)
@app.post('/api/projects')
def add_project():
 d=request.get_json(); fields=['code','name','city','address','project_type','stage','source','owner','client','investor','pm_company','manager','contract_contact','procurement_contact','architect','interior_designer','contractor','phone','mobile','email','website','wood_opportunity','metal_opportunity','cnc_opportunity','doors_opportunity','wall_opportunity','fixed_furniture_opportunity','counter_opportunity','other_opportunity','contract_status','estimated_value','budget','payment_terms','deadline','notes','next_action','next_action_date']; d['code']=d.get('code') or 'TLK-'+datetime.datetime.now().strftime('%y%m%d%H%M%S'); vals=[]
 for f in fields:
  v=d.get(f,'');
  if f.endswith('_opportunity'): v=int(v or 0)
  if f in ('estimated_value','budget'): v=float(v or 0)
  vals.append(v)
 ts=now()
 try: lid=exe(f"INSERT INTO projects({','.join(fields)},created_at,updated_at) VALUES({','.join('?' for _ in fields)},?,?)",vals+[ts,ts])
 except sqlite3.IntegrityError:return jsonify(error='کد پروژه تکراری است.'),400
 return jsonify(one('SELECT * FROM projects WHERE id=?',(lid,)))
@app.put('/api/projects/<int:i>')
def edit_project(i):
 d=request.get_json(); fields=['code','name','city','address','project_type','stage','source','owner','client','investor','pm_company','manager','contract_contact','procurement_contact','architect','interior_designer','contractor','phone','mobile','email','website','wood_opportunity','metal_opportunity','cnc_opportunity','doors_opportunity','wall_opportunity','fixed_furniture_opportunity','counter_opportunity','other_opportunity','contract_status','estimated_value','budget','payment_terms','deadline','notes','next_action','next_action_date']; ss=[];vs=[]
 for f in fields:
  if f in d:
   v=d[f];
   if f.endswith('_opportunity'):v=int(v or 0)
   if f in ('estimated_value','budget'):v=float(v or 0)
   ss.append(f'{f}=?');vs.append(v)
 ss.append('updated_at=?');vs+=[now(),i];exe('UPDATE projects SET '+','.join(ss)+' WHERE id=?',vs);return jsonify(one('SELECT * FROM projects WHERE id=?',(i,)))
@app.delete('/api/projects/<int:i>')
def del_project(i):exe('DELETE FROM projects WHERE id=?',(i,));return jsonify(ok=True)
@app.get('/api/dashboard')
def dash():
 p=allq('SELECT * FROM projects'); [x.update(score=score(x)) for x in p]; today=datetime.date.today().isoformat(); tasks=allq("SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE t.status!='Done' ORDER BY due_date LIMIT 15"); return jsonify(metrics={'projects':len(p),'pipeline':sum(float(x['estimated_value'] or 0) for x in p if x['stage']!='Contract'),'qualified':sum(x['stage'] in ['Opportunity','Meeting','Scope','Proposal','Negotiation'] for x in p),'overdue':len(allq("SELECT * FROM tasks WHERE status!='Done' AND due_date!='' AND due_date<?",(today,)))},projects=sorted(p,key=lambda x:x['score'],reverse=True)[:10],tasks=tasks)
@app.post('/api/contacts')
def contact():
 d=request.get_json(); lid=exe('INSERT INTO contacts(project_id,name,role,company,phone,mobile,email,channel,influence,decision_power,notes,next_action,next_action_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',[d.get(k,'') for k in ['project_id','name','role','company','phone','mobile','email','channel','influence','decision_power','notes','next_action','next_action_date']]);return jsonify(one('SELECT * FROM contacts WHERE id=?',(lid,)))
@app.get('/api/contacts/<int:i>')
def contacts(i):return jsonify(allq('SELECT * FROM contacts WHERE project_id=? ORDER BY decision_power DESC,influence DESC',(i,)))
@app.post('/api/activities')
def activity():
 d=request.get_json();lid=exe('INSERT INTO activities(project_id,contact_id,kind,result,notes,occurred_at,next_action,next_action_date) VALUES(?,?,?,?,?,?,?,?)',[d.get(k,'') for k in ['project_id','contact_id','kind','result','notes','occurred_at','next_action','next_action_date']]);
 if d.get('project_id'):exe('UPDATE projects SET last_contact=?,next_action=?,next_action_date=?,updated_at=? WHERE id=?',[d.get('occurred_at',''),d.get('next_action',''),d.get('next_action_date',''),now(),d['project_id']])
 return jsonify(one('SELECT * FROM activities WHERE id=?',(lid,)))
@app.get('/api/activities/<int:i>')
def acts(i):return jsonify(allq('SELECT a.*,c.name contact_name FROM activities a LEFT JOIN contacts c ON c.id=a.contact_id WHERE a.project_id=? ORDER BY occurred_at DESC',(i,)))
@app.get('/api/tasks')
def tasks():return jsonify(allq('SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id ORDER BY status,due_date'))
@app.post('/api/tasks')
def task():
 d=request.get_json();lid=exe('INSERT INTO tasks(project_id,title,due_date,priority,status,notes,created_at) VALUES(?,?,?,?,?,?,?)',[d.get(k,'') for k in ['project_id','title','due_date','priority','status','notes']]+[now()]);return jsonify(one('SELECT * FROM tasks WHERE id=?',(lid,)))
@app.put('/api/tasks/<int:i>')
def task_edit(i):d=request.get_json();exe('UPDATE tasks SET status=?,priority=?,due_date=?,notes=? WHERE id=?',[d.get('status','Open'),d.get('priority','Medium'),d.get('due_date',''),d.get('notes',''),i]);return jsonify(ok=True)
@app.get('/api/settings')
def settings():
 s=one('SELECT * FROM settings WHERE id=1');s['api_key']='********' if s['api_key'] else '';return jsonify(s)
@app.post('/api/settings')
def save_settings():
 d=request.get_json();cur=one('SELECT * FROM settings WHERE id=1');key=d.get('api_key','');key=cur['api_key'] if key=='********' else key;exe('UPDATE settings SET base_url=?,api_key=?,model=?,temperature=?,max_tokens=?,system_prompt=?,web_enabled=?,updated_at=? WHERE id=1',[d.get('base_url',''),key,d.get('model','gpt-4o'),float(d.get('temperature',.2)),int(d.get('max_tokens',6000)),d.get('system_prompt',''),int(bool(d.get('web_enabled',1))),now()]);return jsonify(ok=True)
@app.post('/api/analyze')
def api_analyze():
 d=request.get_json();
 try:
  payload=analyze(d.get('project_id') or None,d.get('context','')); title=d.get('title') or 'تحلیل Pipeline'; aid=exe('INSERT INTO analyses(title,project_id,payload,created_at) VALUES(?,?,?,?)',[title,d.get('project_id') or None,json.dumps(payload,ensure_ascii=False),now()]);return jsonify(id=aid,title=title,payload=payload)
 except Exception as e:return jsonify(error=str(e)),400
@app.get('/api/analyses')
def analyses():return jsonify(allq('SELECT id,title,project_id,created_at FROM analyses ORDER BY id DESC'))
@app.get('/api/analyses/<int:i>')
def analysis(i):
 x=one('SELECT * FROM analyses WHERE id=?',(i,));
 if not x:return jsonify(error='یافت نشد'),404
 x['payload']=json.loads(x['payload']);return jsonify(x)
@app.post('/api/recommendations/save')
def save_rec():
 d=request.get_json();return jsonify(id=exe('INSERT INTO saved_recommendations(analysis_id,title,payload,created_at) VALUES(?,?,?,?)',[d.get('analysis_id'),d.get('title',''),json.dumps(d.get('payload',{}),ensure_ascii=False),now()]))
@app.get('/api/recommendations/saved')
def saved():
 x=allq('SELECT * FROM saved_recommendations ORDER BY id DESC');
 for a in x:a['payload']=json.loads(a['payload'])
 return jsonify(x)
@app.get('/api/export/<kind>')
def export(kind):
 q={'projects':'SELECT * FROM projects','activities':'SELECT * FROM activities','analyses':'SELECT * FROM analyses'}.get(kind)
 if not q:return jsonify(error='نامعتبر'),400
 p=EXP/f'{kind}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json';p.write_text(json.dumps(allq(q),ensure_ascii=False,indent=2),encoding='utf8');return send_file(p,as_attachment=True,download_name=p.name)
@app.post('/api/import')
def imp():
 f=request.files.get('file');
 if not f:return jsonify(error='فایل انتخاب نشده'),400
 try:
  n=f.filename.lower()
  if n.endswith('.json'):data=json.load(f.stream)
  elif n.endswith('.csv'):data=list(csv.DictReader(io.TextIOWrapper(f.stream,encoding='utf-8-sig')))
  else:
   import openpyxl;wb=openpyxl.load_workbook(f.stream,read_only=True,data_only=True);ws=wb.active;v=list(ws.values);data=[dict(zip(v[0],r)) for r in v[1:]]
  count=0
  for z in data:
   name=z.get('name') or z.get('نام پروژه');
   if not name:continue
   d={'code':'IMP-'+datetime.datetime.now().strftime('%y%m%d%H%M%S')+str(count),'name':name,'city':z.get('city',z.get('شهر','')),'stage':z.get('stage',z.get('مرحله','Lead')),'source':z.get('source',z.get('منبع','Import')),'estimated_value':float(z.get('estimated_value',z.get('ارزش احتمالی',0)) or 0),'notes':z.get('notes',z.get('یادداشت',''))};
   ts=now();exe('INSERT INTO projects(code,name,city,stage,source,estimated_value,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',[d['code'],d['name'],d['city'],d['stage'],d['source'],d['estimated_value'],d['notes'],ts,ts]);count+=1
  return jsonify(imported=count)
 except Exception as e:return jsonify(error=str(e)),400
init()
if __name__=='__main__':app.run(host='127.0.0.1',port=8500,debug=False)
