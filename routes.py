from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder
from werkzeug.utils import secure_filename

main = Blueprint('main', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'csv'}

@main.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'warning')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            upload_dir = os.path.join(os.path.dirname(main.root_path), 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            
            file.save(filepath)

            try:
                df = pd.read_csv(filepath)
                required_columns = ['amount', 'payment_format', 'is_laundering', 'customer_id', 'receiving_bank']
                if not all(col in df.columns for col in required_columns):
                    flash(f'CSV must contain the following columns: {required_columns}', 'danger')
                    return redirect(request.url)

                df.columns = df.columns.str.strip()
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
                df.dropna(subset=['amount'], inplace=True)

                encoder = OneHotEncoder(handle_unknown='ignore')
                ml_features = encoder.fit_transform(df[['payment_format']])
                model = IsolationForest(contamination='auto', random_state=42)
                df['ml_anomaly'] = model.fit_predict(ml_features)

                customer_baselines = df.groupby('customer_id')['amount'].agg(['mean', 'std']).fillna(0)

                def calculate_risk(row):
                    score = 0
                    if row['amount'] > 10000: score += 20
                    if row['amount'] > 50000: score += 30
                    payment_risk = {'cash': 30, 'wire': 20, 'credit': 10, 'debit': 5}
                    score += payment_risk.get(row['payment_format'].lower(), 0)
                    if row['is_laundering'] == 1: score += 50
                    customer_stats = customer_baselines.loc[row['customer_id']]
                    if row['amount'] > customer_stats['mean'] + 2 * customer_stats['std']:
                        score += 25
                    if row['ml_anomaly'] == -1:
                        score += 30
                    return min(score, 100)

                df['risk_score'] = df.apply(calculate_risk, axis=1)
                suspicious_df = df[df['risk_score'] >= 60].sort_values(by='risk_score', ascending=False)
                
                suspicious_alerts = []
                for index, row in suspicious_df.head(20).iterrows():
                    suspicious_alerts.append({
                        'customer': row.get('customer_id', 'N/A'),
                        'amount': row['amount'],
                        'receiving_bank': row.get('receiving_bank', 'N/A'),
                        'risk_score': row['risk_score'],
                        'is_ml_anomaly': row['ml_anomaly'] == -1
                    })

                session['dashboard_data'] = {
                    'total_volume': df['amount'].sum(),
                    'total_transactions': len(df),
                    'payment_formats': df['payment_format'].value_counts().to_dict(),
                    'avg_transaction': df['amount'].mean(),
                    'largest_transaction': df['amount'].max(),
                    'smallest_transaction': df['amount'].min(),
                    'top_banks_by_volume': df.groupby('receiving_bank')['amount'].sum().nlargest(5).to_dict(),
                    'suspicious_alerts': suspicious_alerts
                }
                flash('File successfully processed!', 'success')

            except Exception as e:
                flash(f'An error occurred: {e}', 'danger')
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
            return redirect(url_for('main.index'))

    dashboard_data = session.get('dashboard_data', None)
    return render_template('index.html', data=dashboard_data)

@main.route('/clear')
def clear_session():
    session.pop('dashboard_data', None)
    flash('Dashboard has been cleared.', 'info')
    return redirect(url_for('main.index'))

