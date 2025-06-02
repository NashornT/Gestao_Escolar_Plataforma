from flask import Flask, render_template, request, redirect, flash, send_file
from methods.extract_data import ExtractData
import os
import shutil
from methods.create_school_history import school_history
from methods.download_data import download_school_data
from datetime import datetime

UPLOAD_FOLDER = 'Files'
ALLOWED_EXTENSIONS = {'xls','xlsx'}

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


@app.route('/historico', methods=['POST'])
def historico():
    aluno_nome = request.form.get('aluno')

    output, error = school_history(studant=aluno_nome)

    if error:
        return error, 404

    # Retorna o arquivo para download
    return send_file(output, as_attachment=True, download_name=f"historico_{aluno_nome}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/baixar_dados', methods=['GET'])
def baixar_dados():
    output, error = download_school_data()

    if error:
        return error, 404

    # Retorna o arquivo para download
    return send_file(output, as_attachment=True, download_name=f"dados_alunos_{datetime.now()}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')



if __name__ == '__main__':
    app.run(debug=True)
