from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
import traceback
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
            flash('No file part. Please select a file to upload.', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file. Please select a file to upload.', 'warning')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = None # Initialize filepath
            try:
                upload_dir = os.path.join(os.path.dirname(main.root_path), 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)

                df = pd.read_csv(filepath)
                
                # --- Data Ingestion and Cleaning ---
                # Strip whitespace from headers
                df.columns = df.columns.str.strip()

                # Define the mapping from user's CSV columns to our internal names
                column_mapping = {
                    'Amount Paid': 'amount',
                    'Payment Format': 'payment_format',
                    'Is Laundering': 'is_laundering',
                    'Account': 'customer_id', # Assumes first 'Account' column is the customer
                    'To Bank': 'receiving_bank'
                }

                # Check for required columns from the user's file
                required_user_columns = list(column_mapping.keys())
                # Handle the duplicate 'Account' column by checking for at least one
                if 'Account' not in df.columns:
                     flash(f'CSV must contain an "Account" column for customer ID.', 'danger')
                     return redirect(request.url)

                # Rename columns to our internal standard
                df.rename(columns=column_mapping, inplace=True)
                # The second 'Account' column becomes 'Account.1', which we don't use.

                df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
                df.dropna(subset=['amount'], inplace=True)

                # --- Machine Learning Anomaly Detection ---
                encoder = OneHotEncoder(handle_unknown='ignore')
                ml_features = encoder.fit_transform(df[['payment_format']])
                model = IsolationForest(contamination='auto', random_state=42)
                df['ml_anomaly'] = model.fit_predict(ml_features)

                # --- Analysis and Metrics ---
                customer_baselines = df.groupby('customer_id')['amount'].agg(['mean', 'std']).fillna(0)

                def calculate_risk(row):
                    score = 0
                    if row['amount'] > 10000: score += 20
                    if row['amount'] > 50000: score += 30
                    payment_risk = {'cash': 30, 'wire': 20, 'credit': 10, 'debit': 5}
                    score += payment_risk.get(str(row['payment_format']).lower(), 0)
                    if row['is_laundering'] == 1: score += 50
                    customer_stats = customer_baselines.loc[row['customer_id']]
                    if row['amount'] > customer_stats['mean'] + 2 * customer_stats['std']:
                        score += 25
                    if row['ml_anomaly'] == -1: score += 30
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
                error_message = f"An error occurred during file processing: {str(e)}"
                flash(error_message, 'danger')
                print(traceback.format_exc())
            finally:
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
            return redirect(url_for('main.index'))

    dashboard_data = session.get('dashboard_data', None)
    return render_template('index.html', data=dashboard_data)

@main.route('/clear')
def clear_session():
    session.pop('dashboard_data', None)
    flash('Dashboard has been cleared.', 'info')
    return redirect(url_for('main.index'))

