
import os,binascii
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify
from flask.ext.paginate import Pagination
from flaskext.mysql import MySQL
from config import config
import datetime,json,hashlib

mysql = MySQL()
# create our little application :)

app = Flask(__name__)

for key in config:
    app.config[key] = config[key]

mysql.init_app(app)
app.config.from_object(__name__)

def get_cursor():
    return mysql.connect().cursor()

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def special_exception_handler(error):
    return 'Database connection failed', 500

@app.teardown_appcontext
def close_db():
    """Closes the database again at the end of the request."""
    get_cursor().close()

@app.route('/postblog',methods=['GET','POST'])
def postblog():
	if request.method=="POST":
		return redirect(url_for('shout'))
	return render_template('shout/editor.html')

@app.route('/postit',methods=['GET','POST'])
def postit():
	if request.method=="POST":
		db=get_cursor()
		user = app.config['USERNAME']
		content = request.form['content']
		posttype = int(request.form['ctype'])
		privacytype = int(request.form['ptype'])
		now = datetime.datetime.today()
		if privacytype == 2:
			query = 'insert into AnonymousPosts (Date, PostContent, Type, LikeCount,Name) values ("%s","%s","%s","0","Anonymous")'
			db.execute(query%(now,content,posttype))
			db.execute("commit")
			return redirect(url_for('shout'))
		else:
			likecount=0
			query = 'insert into AnonymousPosts (Date,PostContent,Type,LikeCount,Name) values ("%s","%s","%s","%s","%s")'
			db.execute(query%(now,content,posttype,likecount,user))
			db.execute("commit")
			flash('Posted at '+now.strftime('%d/%m/%y'))
			return redirect(url_for('shout'))
	return redirect(url_for('shout'))

@app.route("/register")
def register():
	return render_template('global/register.html')

@app.route("/add",methods=['POST'])
def add():
	error = None
	db=get_cursor()
	if request.method=='POST':
		uname = str(request.form['username'])
		rollno = str(request.form['rollno'])
		pwd = str(request.form['password1'])
		confirm = str(request.form['password2'])
		email = str(request.form['email'])
		if pwd == confirm:
			sql = 'insert into Login (RollNo,UserName,Password,Role,Email) values ("%s","%s",MD5("%s"),"%s","%s")'%(rollno,uname,pwd,2,email)
			db.execute(sql)
			db.execute("commit")
			flash("Registered Successfully.")
			return redirect(url_for('login'))
		else:
			flash("Failed. Check again")
			return redirect(url_for('register'))
	return redirect(url_for('register'))

@app.route("/login",methods = ['GET','POST'])
def login():
	ip = request.remote_addr
	error = None
	db = get_cursor()
	session['temp']=0
	session.permanent = True
	if request.method=='POST':
		uname=str(request.form['username'])
		pwd=str(request.form['password'])
		sql = 'select Count(*) from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
		db.execute(sql)
		data = db.fetchone()[0]
		if not data:
			error='Invalid username/password'
		else:
			session['logged_in'] = True
			sql='select Role from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
			db.execute(sql)
			result=db.fetchone()[0]
			session['temp']=result
			sql='select Sno from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
			db.execute(sql)
			uid=db.fetchone()[0]
			db.execute("COMMIT")
			app.config['USERNAME'] = uname
			app.config['USERID'] = uid
			flash('You were logged in ')
			return redirect(url_for('mainscreen'))
	return render_template('global/login.html', error=error,UName=app.config['USERNAME'],user_ip=ip)

@app.route('/like')
def like():
	db=get_cursor()
	a = request.args.get('a',0,type=int)
	b = request.args.get('b',0,type=int)
	if a>0:
		shift=0
		sql='select * from like_history where sno=%s and username="%s"'%(a,app.config['USERNAME'])
		db.execute(sql)
		result=db.fetchone()
		if result<=0:
			sql='insert into like_history values(%s,"%s",1)'%(a,app.config['USERNAME'])
		else:
			if result[2]==0:
				sql='delete from like_history where sno=%s and username="%s"'%(a,app.config['USERNAME'])
				shift=1
			else:
				sql='update like_history set activity=1 where sno=%s and username = "%s"'%(a,app.config['USERNAME'])
		db.execute(sql)
		db.execute("commit")
		sql='update anonymousposts set likecount=likecount+1 where sno=%s'%(a)
		db.execute(sql)
		db.execute("commit")
		sql='select likecount from anonymousposts where sno=%s'%(a)
		db.execute(sql)
		res=db.fetchone()[0]
		return jsonify(result1=res,shift=shift)
	elif b>0:
		shift=0
		sql='select * from like_history where sno=%s and username="%s"'%(b,app.config['USERNAME'])
		db.execute(sql)
		result=db.fetchone()
		if result<=0:
			sql='insert into like_history values(%s,"%s",0)'%(b,app.config['USERNAME'])
		else:
			if result[2]==1:
				sql='delete from like_history where sno=%s and username="%s"'%(b,app.config['USERNAME'])
				shift=1
			else:
				sql='update like_history set activity=0 where sno=%s and username = "%s"'%(b,app.config['USERNAME'])
		db.execute(sql)
		db.execute("commit")
		sql='update anonymousposts set likecount=likecount-1 where sno=%s'%(b)
		db.execute(sql)
		db.execute("commit")
		sql='select likecount from anonymousposts where sno=%s'%(b)
		db.execute(sql)
		res=db.fetchone()[0]
		return jsonify(result1=res,shift=shift)

@app.route('/users', strict_slashes=False)
def allusers():
	db=get_cursor()
	sql = 'select * from Profile'
	db.execute(sql)
	users = db.fetchall()
	if not users:
		flash('No users in database')
		return redirect(url_for('shout'))
	else:
		gravatar=[]
		for user in users:
			gravatar.append(hashlib.md5(user[5]).hexdigest())
		return render_template('users.html',users=users,gravatar=gravatar)

# Query for users profile - API using Sno present in database
@app.route('/users/<id_no>', strict_slashes=False)
def users(id_no):
	db=get_cursor()
	sql = 'select * from Profile where Sno=%s'%id_no
	db.execute(sql)
	user = db.fetchone()
	if not user:
		flash('User '+id_no+' not found')
		return redirect(url_for('shout'))
	else:
		gravatar=hashlib.md5(user[5]).hexdigest()
		return render_template('shout/profile.html',user=user,gravatar=gravatar)

# Query for users profile - API using Email registered to user
@app.route('/e-users/<id_email>', strict_slashes=False)
def usersemail(id_email):
	db=get_cursor()
	sql = 'select * from Profile where Email="%s"'%id_email
	db.execute(sql)
	user = db.fetchone()
	if not user:
		flash('Email '+id_email+' not found')
		return redirect(url_for('shout'))
	else:
		return render_template('shout/profile.html',user=user)

@app.route('/logout')
def logout():
    if session['logged_in'] != None:
        if session['logged_in']==True:
            session.pop('logged_in', None)
            session.pop('temp',0)
            flash('You were logged out')
        else:
            flash('Welcome Back!')
    return redirect(url_for('shout'))

@app.route("/filter",methods=['GET'])
def filter():
	search=False
	q=request.args.get('q')
	if q:
		search=True
	try:
		page = int(request.args.get('page',1))
	except ValueError:
		page = 1
	db=get_cursor()
	filter_num=request.args.get('filter',-1,type=int)
	per_page=2
	if page==1:
		start=0
	else:
		start=(page-1)*per_page
	sql = 'select * from AnonymousPosts order by Date desc limit %s,%s'%(start,per_page)
	if filter_num>0:
		sql='select * from AnonymousPosts where Type=%s limit %s,%s'%(filter_num,start,per_page)
	print sql
	db.execute(sql)
	posts=db.fetchall()
	db.execute("commit")
	activity=[]
	i=0
	for post in posts:
		sql='select activity from like_history where sno=%s and username="%s"'%(post[0],app.config['USERNAME'])
		db.execute(sql)
		result=db.fetchone()
		db.execute("commit")
		if result is None:
			like=-1
		else:
			like=int(result[0])
		activity.append(int(like))
		i=i+1
	query='select Count(*) from anonymousposts'
	if filter_num>0:
		query='select Count(*) from anonymousposts where Type=%s'%(filter_num)
	print query
	db.execute(query)
	total=int(db.fetchone()[0])
	db.execute("commit")
	pagination = Pagination(page = page ,per_page=per_page,total = total, search=search,record_name = 'posts',bs_version=3)
	return render_template('shout/screen.html',posts=posts,UName=app.config['USERNAME'],activity=activity,pagination=pagination) #show_entries

@app.route("/")
def mainscreen():
	session['current_page']="welcome"
	return render_template('global/welcome.html')
		
@app.route("/shout")
def shout():
	search=False
	q=request.args.get('q')
	if q:
		search=True
	try:
		page = int(request.args.get('page',1))
	except ValueError:
		page = 1
	db = get_cursor()
	start=0
	per_page=2
	if page==1:
		start=0
	else:
		start=(page-1)*per_page
	sql = 'select * from AnonymousPosts order by Date desc limit %s,%s'%(start,per_page)
	db.execute(sql)
	posts = db.fetchall()
	db.execute("commit")
	activity=[]
	i=0
	for post in posts:
		sql='select activity from like_history where sno=%s and username="%s"'%(post[0],app.config['USERNAME'])
		db.execute(sql)
		result=db.fetchone()
		db.execute("commit")
		if result is None:
			like=-1
		else:
			like=int(result[0])
		activity.append(int(like))
		i=i+1
	query='select Count(*) from anonymousposts'
	db.execute(query)
	total=int(db.fetchone()[0])
	db.execute("commit")
	pagination = Pagination(page = page ,per_page=per_page,total = total, search=search,record_name = 'posts',bs_version=3)
	return render_template('shout/screen.html',posts=posts,UName=app.config['USERNAME'],activity=activity,pagination=pagination) #show_entries
#---------------Buy_Sell---------------
@app.route('/bechde')
def bechde():
	session['current_page']="store"
	return render_template('buysell/index.html')

@app.route('/item/<itemID>')
def show_item_profile(itemID):
	db=get_cursor()
	sql='select * from store where itemID="%s"'%(itemID)
	db.execute(sql)
	details=db.fetchone()
	db.execute("commit")
	sql='select * from profile where sno=%s'%(details[1])
	db.execute(sql)
	uploader=db.fetchone()
	db.execute("commit")
	return render_template('buysell/item_description.html',details=details,uploader=uploader)

@app.route('/store')
def store():
	db=get_cursor()
	sql="select * from store"
	db.execute(sql)
	entries=db.fetchall()
	uploader=[]
	category=[]
	for entry in entries:
		sql='select UserName from login where Sno=%s'%(entry[1])
		db.execute(sql)
		uploader.append(db.fetchone()[0])
		db.execute("commit")
		sql='select CategoryName from store_categories where categoryid=%s'%(entry[4])
		db.execute(sql)
		category.append(db.fetchone())
	db.execute('select distinct CategoryID,CategoryName from store_categories')		
	filter_cat=db.fetchall()
	return render_template('buysell/store.html',entries=entries,uploader=uploader,category=category,filter_cat=filter_cat)

@app.route('/filter_store',methods=['POST'])
def filter_store():
	db=get_cursor()
	category=int(request.form['filter'])
	if category>0:
		sql='select * from store where categoryid="%s"'%(category)
	elif category==0:
		sql="select * from store"
	db.execute(sql)
	entries=db.fetchall()
	uploader=[]
	category=[]
	for entry in entries:
		sql='select UserName from login where RollNo="%s"'%(entry[0])
		db.execute(sql)
		uploader.append(db.fetchone())
		db.execute("commit")
		sql='select CategoryName from store_categories where categoryid=%s'%(entry[4])
		db.execute(sql)
		category.append(db.fetchone())
	db.execute('select distinct CategoryID,CategoryName from store_categories')		
	filter_cat=db.fetchall()
	return render_template('buysell/store.html',entries=entries,uploader=uploader,category=category,filter_cat=filter_cat)

if __name__ == "__main__":
	app.debug = True
	app.secret_key=os.urandom(24)
	app.run(host='0.0.0.0')