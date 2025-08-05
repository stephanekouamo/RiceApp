import os
from io import BytesIO, StringIO
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms.validators import DataRequired, Optional
from wtforms import StringField, PasswordField, SubmitField, DecimalField

app = Flask(__name__)
app.secret_key = 'your_secret_key'
csrf = CSRFProtect(app)
app.config['UPLOAD_FOLDER'] = 'uploads'

df = pd.read_csv('Data_Rice_2022_Python.csv')
df1=df.copy()
rename_dict = {
    'Region': 'Rg',
    'Period': 'Pe',
    'Secondary Culture': 'Sc',
    'Area (ha)': 'Ar',
    'Cultivation practices': 'Cp',
    'Type of crop': 'Tc',
    'Sowing method': 'Sm',
    'Variety type': 'Vt',
    'Variety cycle': 'Vc',
    'Cultivation conditions': 'Cc',
    'Cause of poor conditions': 'Cpc',
    'Quantity of seeds used (kg)': 'Qsu',
    'Classified seed quantity (kg)': 'Csq',
    'Type of spacing': 'Ts',
    'Type of irrigation': 'Ti',
    'Quantity of organic fertiliser (kg)': 'Qof',
    'Quantity of chemical fertiliser (kg)': 'Qcf',
    'Quantity of plant protection product (L)': 'Qppp',
    'Agricultural Equipment': 'Ae',
    'Harvester used': 'Hu',
    'Destination production': 'Dp',
    'Technical support': 'Tu',
    'Estimated production (tonnes)': 'Ep',
    'Number of growing days': 'Ngd',
    'Dry weight (g/m2) /1001': 'Dw',
    'Humidity level/10 (%)': 'Hl',
    'Weight of rice without moisture (g/m2) /1000': 'Wrwm',
    'Yield (T/Ha)': 'Y'
}
# Rename the columns in df1
df1.rename(columns=rename_dict, inplace=True)

user_uploads = {}  # store upload filenames per user_id for dashboard
#introduction of flask form for sing up and login
class SignupForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')
    
class SearchForm(FlaskForm):
    keyword = StringField("Region", validators=[Optional()])
    area_min = DecimalField("Min Area", validators=[Optional()])
    area_max = DecimalField("Max Area", validators=[Optional()])
    submit = SubmitField("Apply")
# Group by Region_name and Variety type name
variety_by_region = df.groupby(['Region_Name', 'Variety type name']).size().reset_index(name='count')
variety_by_region['label'] = variety_by_region['Region_Name'] + ' - ' + variety_by_region['Variety type name']
# Group by region_name and type of irrigation
irrigation_by_region = df.groupby(['Region_Name', 'Type of irrigation name']).size().reset_index(name='count')

# Group by Region and Cultivation Condition, then count occurrences
grouped = df.groupby(['Region_Name', 'Cultivation_condition']).size().reset_index(name='count')
# Calculate total count per Region_Name
total_per_region = grouped.groupby('Region_Name')['count'].transform('sum')
# Compute percentage
grouped['percentage'] = (grouped['count'] / total_per_region) * 100
# Round percentage for clarity (optional)
grouped['percentage'] = grouped['percentage'].round(2)

def init_db():
    with sqlite3.connect('users.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT UNIQUE, password TEXT
            );
        ''')
init_db()

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        pwd = generate_password_hash(form.password.data)
        with sqlite3.connect('users.db') as conn:
            try:
                conn.execute("INSERT INTO users (name,email,password) VALUES (?,?,?)", (name,email,pwd))
                flash('Signup successful!')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Email exists')
    return render_template('signup.html', form=form)

@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        pwd = form.password.data
        with sqlite3.connect('users.db') as conn:
            user = conn.execute("SELECT id,password FROM users WHERE email=?", (email,)).fetchone()
            if user and check_password_hash(user[1], pwd):
                session['user_id'], session['email'] = user[0], email
                return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.clear(); flash('Logged out')
    return redirect(url_for('login'))

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uploads = user_uploads.get(session['user_id'], [])
    summary_table = df.describe().to_html(classes='table table-bordered')
    nulls = df.isnull().sum().to_dict()

    return render_template('dashboard.html', uploads=uploads, summary_table=summary_table, nulls=nulls)

@app.route('/upload', methods=['GET','POST'])
def upload():
    global df
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        f = request.files['file']
        if f and f.filename.lower().endswith('.csv'):
            fn = secure_filename(f.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            f.save(path)
            df = pd.read_csv(path)
            user_uploads.setdefault(session['user_id'], []).append(fn)
            flash('Upload successful')
            return redirect(url_for('dashboard'))  # Redirect to dashboard!
        flash('Please upload a CSV file')
    return render_template('upload.html')

@app.route('/summary')
def summary():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    return render_template('summary.html', nulls=df.isnull().sum().to_dict(), table=df.describe().to_html(classes='table table-bordered'))

@app.route('/export_summary')
def export_summary():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    summary = df.describe()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        summary.to_excel(writer, sheet_name='Summary Stats')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', download_name='summary_statistics.xlsx', as_attachment=True)

@app.route('/search_filter', methods=['GET', 'POST'])
def search_filter():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    form = SearchForm()
    result = None
    if form.validate_on_submit():
        kw = form.keyword.data or ''
        amin = form.area_min.data
        amax = form.area_max.data
        result = df[df['Region_Name'].str.contains(kw, case=False, na=False)]
        if amin is not None:
            result = result[result['Area (ha)'] >= float(amin)]
        if amax is not None:
            result = result[result['Area (ha)'] <= float(amax)]
        session['last_filter'] = result.to_csv(index=False)
    return render_template('search_filter.html', form=form, result=result)
    
#search by region started with the provided keyword
@app.route('/search/regions', methods=['GET'])
def search_regions():
    keyword = request.args.get('keyword', '').lower()
    regions = df['Region_Name'].dropna().unique()
    filtered_regions = [region for region in regions if keyword in region.lower()]
    return render_template('search_results.html', keyword=keyword, results=filtered_regions)

@app.route('/export')
def export():
    if 'user_id' not in session or 'last_filter' not in session:
        flash('No filter to export')
        return redirect(url_for('search_filter'))
    csvdata = session['last_filter']
    # Convert the string data into bytes using utf-8 encoding
    csv_bytes = csvdata.encode('utf-8')
    # Use BytesIO to treat the byte data as a file-like object
    byte_io = BytesIO(csv_bytes)
    return send_file(byte_io, mimetype='text/csv', download_name='filtered_data.csv', as_attachment=True)

@app.route('/export_data')
def export_data():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    csv = df.to_csv(index=False)
    # Convert the CSV string to bytes
    csv_bytes = csv.encode('utf-8')
    # Use BytesIO to create a file-like object in memory
    byte_io = BytesIO(csv_bytes)
    return send_file(byte_io, mimetype='text/csv', download_name='current_dataset.csv', as_attachment=True)

@app.route('/chart')
def charts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    os.makedirs('static/chart', exist_ok=True)

    # Creating and saving various plots with matplotlib
    plt.figure(figsize=(8, 5))
    df.groupby('Region_Name')['Yield (T/Ha)'].mean().plot(kind='bar', color='teal')
    plt.tight_layout()
    plt.savefig('static/chart/bar.png')
    plt.close()
    
    # Create a bar chart for Average area by region
    plt.figure(figsize=(8, 5))
    df.groupby('Region_Name')['Area (ha)'].mean().plot(kind='bar', color='indigo')
    plt.tight_layout()
    plt.savefig('static/chart/area.png')
    plt.close()
    
    # Cultivation condition vs Average Yield
    plt.figure(figsize=(8, 5))
    df.groupby('Cultivation_condition')['Yield (T/Ha)'].mean().plot(kind='bar', color='cyan')
    plt.tight_layout()
    plt.savefig('static/chart/cultivation.png')
    plt.close()

    plt.figure(figsize=(6, 6))
    df['Region_Name'].value_counts().plot(kind='pie', autopct='%1.1f%%')
    plt.tight_layout()
    plt.savefig('static/chart/pie.png')
    plt.close()
    
    plt.figure(figsize=(8, 5))
    df['Yield (T/Ha)'].hist(bins=15, color='coral')
    plt.title('Yield Distribution Histogram')
    plt.xlabel('Yield (T/Ha)')
    plt.ylabel('Frequency')
    plt.tight_layout()
    plt.savefig('static/chart/hist.png')
    plt.close()

    plt.figure(figsize=(8, 5))
    df.sort_values('Period').groupby('Period')['Yield (T/Ha)'].mean().plot(kind='line', marker='o', color='purple')
    plt.title('Yield Trend by Period')
    plt.ylabel('Avg Yield (T/Ha)')
    plt.tight_layout()
    plt.savefig('static/chart/line.png')
    plt.close()

    plt.figure(figsize=(8, 6))
    sns.boxplot(x='Region_Name', y='Yield (T/Ha)', data=df)
    plt.title('Yield by Region (Box Plot)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('static/chart/box.png')
    plt.close()

    plt.figure(figsize=(8, 6))
#    sns.heatmap(df.corr(numeric_only=True), annot=True, cmap='coolwarm')
#    plt.tight_layout()
#    plt.savefig('static/chart/heatmap.png')
#    plt.close()
    # Create the heatmap without x and y axis labels
    sns.heatmap(df.corr(numeric_only=True), annot=True, cmap='coolwarm', cbar=True, xticklabels=False, yticklabels=False)
    # Optionally remove x and y axis labels
    plt.xlabel('')
    plt.ylabel('')
    # Adjust layout to ensure everything fits well
    plt.tight_layout()
    plt.savefig('static/chart/heatmap.png')
    plt.close()
    

    # Create Plotly figure
    # Ensure the columns are numeric (convert them if they are not)
    df['Area (ha)'] = pd.to_numeric(df['Area (ha)'], errors='coerce')
    df['Yield (T/Ha)'] = pd.to_numeric(df['Yield (T/Ha)'], errors='coerce')
    # Create Scatter Plot (Area vs Yield)
    fig_scatter = px.scatter(df, x='Area (ha)', y='Yield (T/Ha)', color='Region_Name', title='Area vs Yield')
    graphJSON_scatter = json.dumps(fig_scatter, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Create Bar Chart for Cultivation Condition by Region
    fig_cultivation_condition = px.bar(df, x='Cultivation_condition', color='Region_Name', 
                                   title='', 
                                   category_orders={'Cultivation_condition': sorted(df['Cultivation_condition'].unique())})
    graphJSON_cultivation_condition = json.dumps(fig_cultivation_condition, cls=plotly.utils.PlotlyJSONEncoder)
    # Create a DataFrame that counts the number of occurrences of each Cultivation Condition
    count_df = df['Cultivation_condition'].value_counts().reset_index()
    count_df.columns = ['Cultivation_condition', 'count']
    
       
    # Create a bar chart for Sowing Method by Region
    fig_sowing_method = px.bar(df, x='Sowing method name', color='Region_Name',
    title='', category_orders={'Sowing method name': sorted(df['Sowing method name'].dropna().unique())})
    graphJSON_sowing_method = json.dumps(fig_sowing_method, cls=plotly.utils.PlotlyJSONEncoder)

    # Create bar chart Variety Type by Region 
    fig_variety_region = px.bar(df, x='Variety type name', color='Region_Name',
    title='', category_orders={'Variety type name': sorted(df['Variety type name'].dropna().unique())})
    graphJSON_variety_region = json.dumps(fig_variety_region, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Create a bar chart Region by Irrigation type 
    fig_irrigation_region = px.bar(df, x='Type of irrigation name', color='Region_Name', 
    title='', category_orders={'Type of irrigation name': sorted(df['Type of irrigation name'].dropna().unique())})
    graphJSON_irrigation_region = json.dumps(fig_irrigation_region, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Create Bar Chart for Count of Cultivation Conditions
    fig_count = px.bar(count_df, 
                   x='Cultivation_condition', 
                   y='count', 
                   title='Count of Cultivation Conditions',
                   labels={'Cultivation_condition': 'Cultivation Condition', 'count': 'Count'},
                   color='Cultivation_condition')
    graphJSON_count = json.dumps(fig_count, cls=plotly.utils.PlotlyJSONEncoder)

    # Now, pass all these variables to the template
    return render_template('chart.html', 
                       graphJSON_scatter=graphJSON_scatter, 
                       graphJSON_cultivation_condition=graphJSON_cultivation_condition, 
                       graphJSON_count=graphJSON_count, graphJSON_sowing_method=graphJSON_sowing_method, 
                       graphJSON_variety_region=graphJSON_variety_region, 
                       graphJSON_irrigation_region=graphJSON_irrigation_region)
if __name__ == '__main__':
    app.run(debug=True)