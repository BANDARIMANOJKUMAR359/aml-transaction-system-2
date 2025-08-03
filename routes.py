from flask import current_app as app
from flask import render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder

@app.route('/')
@app.route('/index')
def index():
    # Check if data is in the session and pass it to the template
    dashboard_data = session.get('dashboard_data', None)
    return render_template('index.html', data=dashboard_data)


# Define the upload folder and allowed extensions
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))
ALLOWED_EXTENSIONS = {'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'warning')
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash(f'File "{filename}" successfully uploaded. Processing data...', 'success')
        # Process the file and store data in the session
        try:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            df = pd.read_csv(filepath)

            # Basic data cleaning
            df['Amount Paid'] = pd.to_numeric(df['Amount Paid'], errors='coerce')
            df.dropna(subset=['Amount Paid', 'Payment Format'], inplace=True)

            # --- Machine Learning Anomaly Detection ---
            # 1. Feature Engineering
            features = df[['Amount Paid', 'Payment Format']]
            encoder = OneHotEncoder(handle_unknown='ignore')
            encoded_formats = encoder.fit_transform(features[['Payment Format']])
            encoded_df = pd.DataFrame(encoded_formats.toarray(), columns=encoder.get_feature_names_out(['Payment Format']))
            
            # Combine numerical and encoded features
            ml_features = pd.concat([df[['Amount Paid']].reset_index(drop=True), encoded_df], axis=1)

            # 2. Train Isolation Forest Model
            model = IsolationForest(contamination='auto', random_state=42)
            df['ml_anomaly'] = model.fit_predict(ml_features)


            # Calculate metrics
            total_volume = df['Amount Paid'].sum()
            total_transactions = len(df)
            payment_format_counts = df['Payment Format'].value_counts().to_dict()

            # --- Detailed Insights ---
            # Flow of Funds
            top_from_banks = df.groupby('From Bank')['Amount Paid'].sum().nlargest(5).to_dict()
            top_to_banks = df.groupby('To Bank')['Amount Paid'].sum().nlargest(5).to_dict()

            # Transaction Analysis
            avg_transaction = df['Amount Paid'].mean()
            max_transaction = df['Amount Paid'].max()
            min_transaction = df['Amount Paid'].min()

            # --- Behavioral Pattern Analysis ---
            # Calculate baseline (average transaction amount per account)
            account_baselines = df.groupby('From Bank')['Amount Paid'].mean().to_dict()

            # --- Dynamic Risk Scoring and Alerts ---
            def calculate_risk_score(row):
                score = 0
                amount = row['Amount Paid']
                from_bank = row['From Bank']

                # 1. Amount-based score (up to 50 points)
                if amount > 500000: score += 50
                elif amount > 100000: score += 40
                elif amount > 10000: score += 15

                # 2. Payment Format-based score (up to 20 points)
                payment_format_risk = {'Cheque': 10, 'Reinvestment': 5, 'Cash': 20, 'Credit Card': 15}
                score += payment_format_risk.get(row['Payment Format'], 10)

                # 3. Behavioral Anomaly score (up to 25 points)
                account_avg = account_baselines.get(from_bank, amount) # Use current amount if no history
                if amount > account_avg * 10: score += 25
                elif amount > account_avg * 5: score += 15

                # 4. Machine Learning Anomaly Score (up to 30 points)
                if row['ml_anomaly'] == -1: # -1 indicates an anomaly
                    score += 30

                # 5. Laundering Flag (heavy penalty)
                if row['Is Laundering'] == 1: score += 100

                return min(score, 100)


            df['risk_score'] = df.apply(calculate_risk_score, axis=1)
            risk_threshold = 60 # Alert if risk score is above 60
            suspicious_transactions = df[df['risk_score'] > risk_threshold].sort_values(by='risk_score', ascending=False)

            alerts = []
            for index, row in suspicious_transactions.head(20).iterrows(): # Show top 20 alerts
                score = int(row['risk_score'])
                if score > 90:
                    risk_level = 'critical'
                elif score > 70:
                    risk_level = 'high'
                elif score > 50:
                    risk_level = 'medium'
                else:
                    risk_level = 'low'

                alerts.append({
                    'Timestamp': row['Timestamp'],
                    'From_Bank': row['From Bank'],
                    'To_Bank': row['To Bank'],
                    'Amount': f"{row['Amount Paid']:,.2f}",
                    'Risk_Score': score,
                    'Risk_Level': risk_level,
                    'is_ml_anomaly': row['ml_anomaly'] == -1
                })

            # Store data in session
            session['dashboard_data'] = {
                'filename': filename,
                'total_volume': f'{total_volume:,.2f}',
                'total_transactions': f'{total_transactions:,}',
                'payment_formats': payment_format_counts,
                'top_from_banks': {str(k): f'{v:,.2f}' for k, v in top_from_banks.items()},
                'top_to_banks': {str(k): f'{v:,.2f}' for k, v in top_to_banks.items()},
                'avg_transaction': f'{avg_transaction:,.2f}',
                'max_transaction': f'{max_transaction:,.2f}',
                'min_transaction': f'{min_transaction:,.2f}',
                'alerts': alerts
            }

        except Exception as e:
            flash(f'Error processing file: {e}', 'danger')
            return redirect(url_for('index'))

        return redirect(url_for('index'))
    else:
        flash('Invalid file type. Please upload a CSV file.', 'danger')
        return redirect(url_for('index'))
