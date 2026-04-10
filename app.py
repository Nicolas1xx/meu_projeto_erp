import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

# Configuração Inicial
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lh_erp_secure_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp_lh.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELOS DE BANCO DE DADOS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Faturamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_slug = db.Column(db.String(50)) # 'leao' ou 'health'
    categoria = db.Column(db.String(100))
    valor = db.Column(db.Float)
    vencimento = db.Column(db.Date)
    status = db.Column(db.String(20), default='Pendente')
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)

class Colaborador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_slug = db.Column(db.String(50))
    nome = db.Column(db.String(100))
    cpf = db.Column(db.String(14))
    tipo_contrato = db.Column(db.String(20)) # CLT ou PJ
    cargo = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Ativo')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTAS DE NAVEGAÇÃO E LOGIN ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('selecao'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Recebe o CPF vindo do formulário (com ou sem máscara)
        cpf_input = request.form.get('cpf')
        password_input = request.form.get('password')
        
        # Busca no banco pelo CPF exato
        user = User.query.filter_by(cpf=cpf_input).first()
        
        if user and user.password == password_input:
            login_user(user)
            return redirect(url_for('selecao'))
        
        flash('CPF ou Senha incorretos. Tente novamente.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

# --- SELEÇÃO DE EMPRESA ---

@app.route('/selecao')
@login_required
def selecao():
    return render_template('selecao.html', nome=current_user.name)

@app.route('/set_empresa/<empresa_id>')
@login_required
def set_empresa(empresa_id):
    # Dicionário para converter o slug em nome amigável
    nomes = {'leao': 'Leão Serviços', 'health': 'Health Max'}
    
    if empresa_id in nomes:
        session['empresa_ativa'] = nomes[empresa_id]
        session['empresa_slug'] = empresa_id
        return redirect(url_for('dashboard'))
    return redirect(url_for('selecao'))

# --- MÓDULOS DO ERP ---

@app.route('/dashboard')
@login_required
def dashboard():
    empresa = session.get('empresa_ativa', 'Grupo L&H')
    return render_template('dashboard.html', empresa=empresa)

@app.route('/faturamento')
@login_required
def faturamento():
    empresa = session.get('empresa_ativa')
    slug = session.get('empresa_slug')
    # Filtra os dados no banco pela empresa selecionada
    dados = Faturamento.query.filter_by(empresa_slug=slug).all()
    return render_template('faturamento.html', empresa=empresa, lancamentos=dados)

@app.route('/rh')
@login_required
def rh():
    empresa = session.get('empresa_ativa')
    slug = session.get('empresa_slug')
    equipe = Colaborador.query.filter_by(empresa_slug=slug).all()
    return render_template('rh.html', empresa=empresa, colaboradores=equipe)

@app.route('/contratos')
@login_required
def contratos():
    empresa = session.get('empresa_ativa')
    return render_template('contratos.html', empresa=empresa)

# --- INICIALIZAÇÃO DO SISTEMA ---

def setup_erp():
    """Cria o banco de dados e o usuário mestre do Nicolas"""
    with app.app_context():
        db.create_all()
        
        # Verifica se o Nicolas já está cadastrado
        nicolas_cpf = "000.000.000-00"
        if not User.query.filter_by(cpf=nicolas_cpf).first():
            admin = User(
                name="Nicolas Silva",
                cpf=nicolas_cpf,
                password="123" # Senha padrão inicial
            )
            db.session.add(admin)
            db.session.commit()
            print(">>> Banco de dados criado e usuário mestre (Nicolas) cadastrado.")

if __name__ == '__main__':
    setup_erp()
    app.run(debug=True)