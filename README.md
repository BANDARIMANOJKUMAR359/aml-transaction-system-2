# AML Transaction Monitoring System

A web-based dashboard for analyzing financial transaction data to detect potential money laundering activities, built with Flask and scikit-learn.

## Core Features

- **Engaging Dashboard**: Visualizes key transaction metrics, including total volume, transaction counts, and flow of funds.
- **File Upload**: Supports uploading CSV files for on-the-fly analysis.
- **Dynamic Risk Scoring**: A multi-layered engine that assigns a risk score to each transaction based on amount, payment type, and behavioral patterns.
- **Behavioral Pattern Analysis**: Detects deviations from a customer's normal transaction history to flag unusual activity.
- **Machine Learning Anomaly Detection**: Uses an `IsolationForest` model to identify complex and subtle anomalies that rule-based systems might miss.

## Deployment

This application is ready for deployment. Follow these steps to get it live on the web for free using Render. This will bypass all local environment issues.

### Step 1: Create a GitHub Repository

1.  Go to [GitHub](https://github.com) and create a free account if you don't have one.
2.  Create a **new public repository**. You can name it `aml-transaction-system`.
3.  Upload all the files from the `c:\Users\681673\.windsurf\aml-system` directory into this new repository.

### Step 2: Deploy to Render

1.  **Click the button below.** This will take you to Render to deploy your application.

    [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME)

    **Important:** Before clicking, you must copy the URL of the GitHub repository you just created and replace the placeholder in the link above.
    - **How to do it:** Right-click the "Deploy to Render" button, copy the link, paste it somewhere, and replace `https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME` with your actual GitHub repository URL.

2.  **On the Render site:**
    - Give your web service a unique name.
    - Render will automatically detect the settings from your `requirements.txt` and `Procfile`.
    - Click **"Create Web Service"** at the bottom of the page.

Render will now build and deploy your application. After a few minutes, it will provide you with a public URL where you can access your live AML dashboard. Thank you for your patience through the debugging process; this will get you the final, working result.
