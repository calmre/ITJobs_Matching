# IT Jobs Matcher

A Streamlit web application that matches user skills and preferences against a dataset of IT jobs. It uses TF-IDF and cosine similarity to find the best job matches based on your tech specialisation, experience level, work mode, job type, and salary expectations.

## Features
- **Smart Matching:** Uses Natural Language Processing (TF-IDF & Cosine Similarity) to analyze your skill query against job job requirements.
- **Interactive UI:** Built with Streamlit for a clean, interactive user experience.
- **Data Visualizations:** Utilizes Plotly to provide insights into the job market.

## Setup Instructions

1. Clone this repository:
   ```bash
   git clone <your-repo-url>
   cd itjobs_matching
   ```

2. Create a virtual environment (Optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate  # On Windows
   ```

3. Install the necessary dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```
