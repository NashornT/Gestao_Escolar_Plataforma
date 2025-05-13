from flask import Flask, render_template, request, redirect, flash
import os
from extract_data import ExtractData
import os
import shutil

UPLOAD_FOLDER = 'Files'
ALLOWED_EXTENSIONS = {'xls'}

app = Flask(__name__)
app.secret_key = 'sua_chave_super_secreta'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'files' not in request.files:
            flash('Nenhum arquivo enviado.')
            return redirect(request.url)

        files = request.files.getlist('files')  # Obter todos os arquivos enviados
        if not files or all(file.filename == '' for file in files):
            flash('Nenhum arquivo selecionado.')
            return redirect(request.url)

        for file in files:
            if file and allowed_file(file.filename):
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                filepath = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(filepath)
            else:
                flash(f'Tipo de arquivo inválido: {file.filename}. Use apenas arquivos .xls.')

        try:
            ExtractData(folder_path=UPLOAD_FOLDER).run()
            flash('Arquivo processado com sucesso!')
        except Exception as e:
            flash(f'Ocorreu um erro durante o processamento: {str(e)}')

        shutil.rmtree(UPLOAD_FOLDER)

        return redirect(request.url)

    return render_template('index.html')

@app.route('/relatorio', methods=['GET'])
def relatorio():
    return redirect("http://localhost:8501")


if __name__ == '__main__':
    app.run(debug=True)
