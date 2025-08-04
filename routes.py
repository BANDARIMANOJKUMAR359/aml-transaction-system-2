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
                suspicious_alerts = []
                total_volume = 0
                total_transactions = 0
                payment_formats = Counter()
                largest_transaction = 0
                smallest_transaction = float('inf')
                top_from_banks = Counter()
                top_to_banks = Counter()

                # Manually read the header to handle duplicate columns robustly
                with open(filepath, 'r') as f:
                    header = f.readline().strip().split(',')
                original_columns = [col.strip() for col in header]

                if original_columns.count('Account') < 2:
                    flash('Error: The uploaded CSV file must contain at least two columns named "Account" (for From and To).', 'danger')
                    return redirect(request.url)

                new_cols = []
                acc_count = 0
                for col in original_columns:
                    if col == 'Account':
                        new_cols.append('from_account' if acc_count == 0 else 'to_account')
                        acc_count += 1
                    else:
                        new_cols.append(col)

                all_chunks = []
                for chunk in pd.read_csv(filepath, chunksize=chunk_size, header=0, names=new_cols, skiprows=1):
                    all_chunks.append(chunk)
                
                if not all_chunks:
                    flash('CSV file is empty or invalid.', 'danger')
                    return redirect(request.url)

                df = pd.concat(all_chunks, ignore_index=True)
                df.rename(columns={
                    'Amount Paid': 'amount',
                    'Payment Format': 'payment_format',
                    'Is Laundering': 'is_laundering',
                    'From Bank': 'from_bank',
                    'To Bank': 'to_bank',
                    'Timestamp': 'timestamp'
                }, inplace=True)

                df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
                df.dropna(subset=['amount'], inplace=True)

                total_volume = df['amount'].sum()
                total_transactions = len(df)
                payment_formats.update(df['payment_format'])
                largest_transaction = df['amount'].max()
                smallest_transaction = df['amount'].min()
                top_from_banks.update(df.groupby('from_bank')['amount'].sum().to_dict())
                top_to_banks.update(df.groupby('to_bank')['amount'].sum().to_dict())

                encoder = OneHotEncoder(handle_unknown='ignore')
                ml_features = encoder.fit_transform(df[['payment_format']])
                model = IsolationForest(contamination='auto', random_state=42)
                df['ml_anomaly'] = model.fit_predict(ml_features)

                customer_baselines = df.groupby('from_account')['amount'].agg(['mean', 'std']).fillna(0)

                def calculate_risk(row):
                    score = 0
                    if row['amount'] > 1000000: score += 25
                    elif row['amount'] > 50000: score += 15
                    elif row['amount'] > 10000: score += 5
                    payment_risk = {'cash': 15, 'wire': 10, 'credit': 5, 'debit': 0}
                    score += payment_risk.get(str(row.get('payment_format', '')).lower(), 0)
                    if row.get('is_laundering') == 1: score += 35
                    if row['from_account'] in customer_baselines.index:
                        stats = customer_baselines.loc[row['from_account']]
                        if stats['std'] > 0 and row['amount'] > stats['mean'] + 3 * stats['std']: score += 20
                    if row['ml_anomaly'] == -1: score += 20
                    return min(score, 100)

                df['risk_score'] = df.apply(calculate_risk, axis=1)
                df['risk_level'] = pd.cut(df['risk_score'], bins=[-1, 40, 70, 101], labels=['Low', 'Medium', 'High'])
                suspicious_df = df[df['risk_score'] >= 50].sort_values(by='risk_score', ascending=False)

                for _, row in suspicious_df.head(20).iterrows():
                    suspicious_alerts.append({
                        'Timestamp': row.get('timestamp', 'N/A'),
                        'From_Bank': row.get('from_bank', 'N/A'),
                        'From_Account': row.get('from_account', 'N/A'),
                        'To_Bank': row.get('to_bank', 'N/A'),
                        'To_Account': row.get('to_account', 'N/A'),
                        'Amount': f"{row['amount']:,.2f}",
                        'Risk_Score': int(row['risk_score']),
                        'Risk_Level': row['risk_level'],
                        'ML_Anomaly': row['ml_anomaly']
                    })

                session['dashboard_data'] = {
                    'filename': filename,
                    'total_volume': f'{total_volume:,.2f}',
                    'total_transactions': f'{total_transactions:,}',
                    'payment_formats': dict(payment_formats.most_common(5)),
                    'avg_transaction': f'{total_volume / total_transactions if total_transactions > 0 else 0:,.2f}',
                    'max_transaction': f'{largest_transaction:,.2f}',
                    'min_transaction': f'{smallest_transaction if total_transactions > 0 else 0:,.2f}',
                    'top_from_banks': dict(top_from_banks.most_common(5)),
                    'top_to_banks': dict(top_to_banks.most_common(5)),
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
