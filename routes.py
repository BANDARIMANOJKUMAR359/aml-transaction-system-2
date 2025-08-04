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
                chunk_size = 10000
                alerts = []
                total_volume = 0
                total_transactions = 0
                payment_formats = Counter()
                largest_transaction = 0
                smallest_transaction = float('inf')
                top_from_banks = Counter()
                top_to_banks = Counter()

                # Use a more robust way to handle duplicate 'Account' columns
                # Read the header to get original column names
                original_columns = pd.read_csv(filepath, nrows=0).columns.tolist()

                # Find indices of 'Account' columns
                account_indices = [i for i, col in enumerate(original_columns) if col == 'Account']

                # Process the file in chunks
                for chunk in pd.read_csv(filepath, chunksize=chunk_size, header=0, names=original_columns):
                    chunk.columns = [f"{col}_{i}" if col == 'Account' else col for i, col in enumerate(original_columns)]
                    
                    column_mapping = {
                        'Amount Paid': 'amount',
                        'Payment Format': 'payment_format',
                        'Is Laundering': 'is_laundering',
                        f'Account_{account_indices[0]}': 'from_account',
                        f'Account_{account_indices[1]}': 'to_account',
                        'From Bank': 'from_bank',
                        'To Bank': 'to_bank',
                        'Timestamp': 'timestamp'
                    }

                    chunk.columns = chunk.columns.str.strip()
                    chunk.rename(columns=column_mapping, inplace=True)

                    chunk['amount'] = pd.to_numeric(chunk['amount'], errors='coerce')
                    chunk.dropna(subset=['amount'], inplace=True)

                    if chunk.empty:
                        continue

                    total_volume += chunk['amount'].sum()
                    total_transactions += len(chunk)
                    payment_formats.update(chunk['payment_format'])
                    largest_transaction = max(largest_transaction, chunk['amount'].max())
                    smallest_transaction = min(smallest_transaction, chunk['amount'].min())
                    top_from_banks.update(chunk.groupby('from_bank')['amount'].sum().to_dict())
                    top_to_banks.update(chunk.groupby('to_bank')['amount'].sum().to_dict())

                    encoder = OneHotEncoder(handle_unknown='ignore')
                    ml_features = encoder.fit_transform(chunk[['payment_format']])
                    model = IsolationForest(contamination='auto', random_state=42)
                    chunk['ml_anomaly'] = model.fit_predict(ml_features)

                    # Use 'from_account' as the customer identifier
                    customer_baselines = chunk.groupby('from_account')['amount'].agg(['mean', 'std']).fillna(0)

                    def calculate_risk(row):
                        score = 0
                        if row['amount'] > 10000: score += 20
                        if row['amount'] > 50000: score += 30
                        payment_risk = {'cash': 30, 'wire': 20, 'credit': 10, 'debit': 5}
                        score += payment_risk.get(str(row['payment_format']).lower(), 0)
                        if row['is_laundering'] == 1: score += 50
                        if row['from_account'] in customer_baselines.index:
                            customer_stats = customer_baselines.loc[row['from_account']]
                            if row['amount'] > customer_stats['mean'] + 2 * customer_stats['std']:
                                score += 25
                        if row['ml_anomaly'] == -1: score += 30
                        return min(score, 100)

                    chunk['risk_score'] = chunk.apply(calculate_risk, axis=1)
                    suspicious_df = chunk[chunk['risk_score'] >= 60]

                    for index, row in suspicious_df.iterrows():
                        alerts.append({
                            'Timestamp': row.get('timestamp', 'N/A'),
                            'From_Bank': row.get('from_bank', 'N/A'),
                            'From_Account': row.get('from_account', 'N/A'),
                            'To_Bank': row.get('to_bank', 'N/A'),
                            'To_Account': row.get('to_account', 'N/A'),
                            'Amount': f"{row['amount']:,.2f}",
                            'Risk_Score': row['risk_score'],
                            'is_ml_anomaly': row['ml_anomaly'] == -1
                        })
                
                alerts.sort(key=lambda x: x['Risk_Score'], reverse=True)

                session['dashboard_data'] = {
                    'filename': filename,
                    'total_volume': f'{total_volume:,.2f}',
                    'total_transactions': f'{total_transactions:,}',
                    'payment_formats': dict(payment_formats),
                    'avg_transaction': f'{total_volume / total_transactions if total_transactions > 0 else 0:,.2f}',
                    'max_transaction': f'{largest_transaction:,.2f}',
                    'min_transaction': f'{smallest_transaction if smallest_transaction != float("inf") else 0:,.2f}',
                    'top_from_banks': {str(k): f'{v:,.2f}' for k, v in top_from_banks.most_common(5)},
                    'top_to_banks': {str(k): f'{v:,.2f}' for k, v in top_to_banks.most_common(5)},
                    'alerts': alerts[:20]
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

