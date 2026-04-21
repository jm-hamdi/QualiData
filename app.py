import io
import uuid
from datetime import datetime

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

from core.cleaner import clean_dataframe
from core.reporter import build_json_summary, generate_csv_report, generate_excel_report

app = Flask(__name__)

SESSION_STORE = {}


# ── Helper ─────────────────────────────────────────────────────────────────────

def _read_file(file) -> pd.DataFrame:
    filename = file.filename.lower()
    if filename.endswith('.csv'):
        for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
            try:
                file.seek(0)
                return pd.read_csv(file, encoding=enc)
            except Exception:
                continue
        raise ValueError("Unable to read CSV with supported encodings")
    elif filename.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file)
    raise ValueError(f"Unsupported file format: {file.filename}")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    try:
        df = _read_file(file)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        'df_json': df.to_json(orient='records', force_ascii=False),
        'columns': list(df.columns),
        'filename': file.filename,
    }

    return jsonify({
        'session_id': session_id,
        'rows': len(df),
        'columns': list(df.columns),
        'preview': df.head(5).to_dict(orient='records'),
        'filename': file.filename,
    })


@app.route('/api/analyze', methods=['POST'])
def analyze():
    body = request.get_json(silent=True) or {}
    session_id = body.get('session_id')
    if not session_id or session_id not in SESSION_STORE:
        return jsonify({'error': 'Invalid session'}), 400

    session = SESSION_STORE[session_id]
    df = pd.read_json(io.StringIO(session['df_json']), orient='records')

    results = clean_dataframe(df)
    # Store results for download
    session['results'] = results
    session['df_clean_json'] = results['df_clean'].to_json(orient='records', force_ascii=False)

    return jsonify(build_json_summary(results))


@app.route('/api/download/<fmt>', methods=['POST'])
def download(fmt):
    body = request.get_json(silent=True) or {}
    session_id = body.get('session_id')
    if not session_id or session_id not in SESSION_STORE:
        return jsonify({'error': 'Invalid session'}), 400

    session = SESSION_STORE[session_id]
    if 'results' not in session:
        return jsonify({'error': 'No analysis results found'}), 400

    results = session['results']
    df_clean = pd.read_json(io.StringIO(session['df_clean_json']), orient='records')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if fmt == 'excel':
        data = generate_excel_report(df_clean, results)
        filename = f'qualidata_rapport_{timestamp}.xlsx'
        mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return send_file(
            io.BytesIO(data),
            mimetype=mime,
            as_attachment=True,
            download_name=filename,
        )
    elif fmt == 'csv':
        data = generate_csv_report(df_clean)
        filename = f'qualidata_clean_{timestamp}.csv'
        return send_file(
            io.BytesIO(data),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename,
        )
    return jsonify({'error': 'Unknown format'}), 400


if __name__ == '__main__':
    app.run(port=5000, debug=True)
