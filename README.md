PayRecover AI — Intelligent Payment Recovery & Risk Analytics

Overview

PayRecover AI is a Python-based payment recovery analytics prototype built with Streamlit. It helps users review payment records, monitor outstanding balances, analyze overdue accounts, and explore recovery scenarios.

Key Features

- Collection Overview: View billed amounts, collected amounts, pending balances, and risk-related exposure.
- Payment Analytics: Explore payment status and collection data through interactive visualizations.
- Risk Analysis: Review payment records grouped by risk category.
- Customer Analysis: Compare customer payment positions and identify overdue accounts.
- Overdue Monitoring: Review overdue records and prepare follow-up messages.
- Recovery What-if Simulator: Estimate potential additional collections using a user-selected recovery rate.
- Payment Record Management: Add, filter, review, and manage payment records.
- CSV/Excel Import: Upload payment files, validate required columns, preview records, and confirm import.
- Reminder Previews: Prepare editable reminder messages; messages are not sent automatically.

Technology Stack

- Python
- Streamlit
- Pandas
- Plotly
- SQLite

Run Locally

Install the dependencies:

"pip install -r requirements.txt"

Start the application:

"python -m streamlit run app.py"

Current Scope and Limitations

This prototype uses a local SQLite database. It does not connect directly to Razorpay, process real payments, or send live reminders. The recovery simulator provides scenario estimates and should not be interpreted as a predictive AI model.

Secure multi-company access and AI-driven recovery recommendations are future development goals.

Project Objective

To make payment recovery analysis more accessible by combining collection visibility, overdue monitoring, risk analysis, and recovery scenario planning in one dashboard.
