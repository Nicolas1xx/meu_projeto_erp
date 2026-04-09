import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lh_group_security_key_2026_pro' # Chave de segurança da sessão
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp_lh.db' # Banco de Dados local
app.config['UPLOAD_FOLDER'] = 'static/uploads' # Pasta para Notas Fiscais e Contratos
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16MB por arquivo

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELOS DE BANCO DE DADOS ---

# Tabela de Usuários (Administradores/Colaboradores)
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    senha = db.Column(db.String(128), nullable=False)
    nome = db.Column(db.String(100), nullable=True)

# Tabela de Documentos (Uploads de NF, Empenhos, Contratos)
class Documento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    tipo = db.Column(db.String(50)) # NF, Contrato, Boleto
    empresa = db.Column(db.String(20)) # LEAO ou HEALTH
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cpf_input = request.form.get('cpf').replace('.', '').replace('-', '')
        senha_input = request.form.get('senha')
        
        user = Usuario.query.filter_by(cpf=cpf_input).first()
        
        # LOGICA DE PRIMEIRO ACESSO: Cria o admin se o banco estiver vazio
        if not user and cpf_input == '12345678900':
            admin_user = Usuario(
                cpf='12345678900', 
                senha=generate_password_hash('123456'),
                nome="Administrador Nicolas"
            )
            db.session.add(admin_user)
            db.session.commit()
            user = admin_user

        if user and check_password_hash(user.senha, senha_input):
            login_user(user)
            return redirect(url_for('selecao'))
        
        flash('CPF ou Senha incorretos. Tente novamente.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear() # Limpa a empresa selecionada
    return redirect(url_for('login'))

# --- ROTAS DE NAVEGAÇÃO ---

@app.route('/selecao')
@login_required
def selecao():
    return render_template('selecao.html')

@app.route('/set_empresa/<empresa>')
@login_required
def set_empresa(empresa):
    # Define qual CNPJ o sistema vai operar nesta sessão
    if empresa == 'leao':
        session['empresa_nome'] = "LEÃO SERVIÇOS"
        session['empresa_slug'] = "leao"
    else:
        session['empresa_nome'] = "HEALTH MAX"
        session['empresa_slug'] = "health"
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', empresa=session.get('empresa_nome'))

@app.route('/faturamento')
@login_required
def faturamento():
    return render_template('faturamento.html', empresa=session.get('empresa_nome'))

@app.route('/rh')
@login_required
def rh():
    return render_template('rh.html', empresa=session.get('empresa_nome'))

@app.route('/contratos')
@login_required
def contratos():
    return render_template('contratos.html', empresa=session.get('empresa_nome'))

# --- LOGICA DE UPLOAD PROFISSIONAL ---

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo selecionado')
        return redirect(request.referrer)
    
    file = request.files['arquivo']
    tipo_doc = request.form.get('tipo_doc', 'Outros')
    
    if file.filename == '':
        flash('Nome de arquivo inválido')
        return redirect(request.referrer)

    if file:
        filename = secure_filename(file.filename)
        # Organiza pastas por empresa: uploads/leao/ ou uploads/health/
        empresa_folder = session.get('empresa_slug', 'geral')
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], empresa_folder)
        
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
            
        file.save(os.path.join(upload_path, filename))
        
        # Salva o registro no banco de dados
        novo_doc = Documento(
            filename=filename, 
            tipo=tipo_doc, 
            empresa=session.get('empresa_slug')
        )
        db.session.add(novo_doc)
        db.session.commit()
        
        flash(f'Documento "{filename}" enviado com sucesso!', 'success')
        return redirect(request.referrer)

# --- INICIALIZAÇÃO DO SERVIDOR ---

if __name__ == '__main__':
    with app.app_context():
        # Cria as tabelas se elas não existirem
        db.create_all()
        # Cria a pasta de uploads inicial
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
    print(">>> Sistema do Grupo L&H Iniciado com Sucesso!")
    app.run(debug=True)