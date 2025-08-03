from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
import traceback
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder
from werkzeug.utils import secure_filename
from collections import Counter

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
            filepath = None
            try:
                upload_dir = os.path.join(os.path.dirname(main.root_path), 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)

                # --- Memory-Efficient Processing ---
                chunk_size = 10000  # Process 10,000 rows at a time
                suspicious_alerts = []
                total_volume = 0
                total_transactions = 0
                payment_formats = Counter()
                largest_transaction = 0
                smallest_transaction = float('inf')
                top_banks_by_volume = Counter()

                # Define the mapping from user's CSV columns to our internal names
                column_mapping = {
                    'Amount Paid': 'amount',
                    'Payment Format': 'payment_format',
                    'Is Laundering': 'is_laundering',
                    'Account': 'customer_id',
                    'To Bank': 'receiving_bank'
                }

                # First, get the headers to check them
                df_head = pd.read_csv(filepath, nrows=0)
                df_head.columns = df_head.columns.str.strip()
                if 'Account' not in df_head.columns:
                    flash('CSV must contain an "Account" column for customer ID.', 'danger')
                    return redirect(request.url)

                # Process the file in chunks
                for chunk in pd.read_csv(filepath, chunksize=chunk_size):
                    chunk.columns = chunk.columns.str.strip()
                    chunk.rename(columns=column_mapping, inplace=True)

                    chunk['amount'] = pd.to_numeric(chunk['amount'], errors='coerce')
                    chunk.dropna(subset=['amount'], inplace=True)

                    if chunk.empty:
                        continue

                    # --- Update Aggregates ---
                    total_volume += chunk['amount'].sum()
                    total_transactions += len(chunk)
                    payment_formats.update(chunk['payment_format'])
                    largest_transaction = max(largest_transaction, chunk['amount'].max())
                    smallest_transaction = min(smallest_transaction, chunk['amount'].min())
                    top_banks_by_volume.update(chunk.groupby('receiving_bank')['amount'].sum().to_dict())

                    # --- ML and Risk Scoring (on the chunk) ---
                    encoder = OneHotEncoder(handle_unknown='ignore')
                    ml_features = encoder.fit_transform(chunk[['payment_format']])
                    model = IsolationForest(contamination='auto', random_state=42)
                    chunk['ml_anomaly'] = model.fit_predict(ml_features)

                    customer_baselines = chunk.groupby('customer_id')['amount'].agg(['mean', 'std']).fillna(0)

                    def calculate_risk(row):
                        score = 0
                        if row['amount'] > 10000: score += 20
                        if row['amount'] > 50000: score += 30
                        payment_risk = {'cash': 30, 'wire': 20, 'credit': 10, 'debit': 5}
                        score += payment_risk.get(str(row['payment_format']).lower(), 0)
                        if row['is_laundering'] == 1: score += 50
                        if row['customer_id'] in customer_baselines.index:
                            customer_stats = customer_baselines.loc[row['customer_id']]
                            if row['amount'] > customer_stats['mean'] + 2 * customer_stats['std']:
                                score += 25
                        if row['ml_anomaly'] == -1: score += 30
                        return min(score, 100)

                    chunk['risk_score'] = chunk.apply(calculate_risk, axis=1)
                    suspicious_df = chunk[chunk['risk_score'] >= 60]

                    for index, row in suspicious_df.iterrows():
                        suspicious_alerts.append({
                            'customer': row.get('customer_id', 'N/A'),
                            'amount': row['amount'],
                            'receiving_bank': row.get('receiving_bank', 'N/A'),
                            'risk_score': row['risk_score'],
                            'is_ml_anomaly': row['ml_anomaly'] == -1
                        })
                
                # Sort all alerts by risk score and take the top 20
                suspicious_alerts.sort(key=lambda x: x['risk_score'], reverse=True)

                session['dashboard_data'] = {
                    'total_volume': total_volume,
                    'total_transactions': total_transactions,
                    'payment_formats': dict(payment_formats),
                    'avg_transaction': total_volume / total_transactions if total_transactions > 0 else 0,
                    'largest_transaction': largest_transaction,
                    'smallest_transaction': smallest_transaction if smallest_transaction != float('inf') else 0,
                    'top_banks_by_volume': dict(top_banks_by_volume.most_common(5)),
                    'suspicious_alerts': suspicious_alerts[:20]
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

