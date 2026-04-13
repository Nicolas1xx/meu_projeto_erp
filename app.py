import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from werkzeug.utils import secure_filename

# --- CONFIGURAÇÃO DO SISTEMA ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lh_erp_nicolas_2026_secure'
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

class ContaReceber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_slug = db.Column(db.String(50))
    mes_referencia = db.Column(db.String(20))
    status = db.Column(db.String(50))
    cidade = db.Column(db.String(100))
    servico = db.Column(db.String(100))
    nf = db.Column(db.String(50))
    empresa_planilha = db.Column(db.String(100))
    emissao_nota = db.Column(db.String(50))
    vencimento = db.Column(db.String(50))
    valor_nota = db.Column(db.Float, default=0.0)
    iss_retido = db.Column(db.String(20))
    valor_iss = db.Column(db.Float, default=0.0)
    porcentagem = db.Column(db.String(20))
    valor_ir = db.Column(db.Float, default=0.0)
    valor_liquido = db.Column(db.Float, default=0.0)
    valor_recebido = db.Column(db.Float, default=0.0)
    diferenca = db.Column(db.Float, default=0.0)
    data_pg = db.Column(db.String(50))
    observacoes = db.Column(db.String(255))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- FUNÇÕES DE APOIO ---
def to_float(val):
    if val is None or val == '': return 0.0
    if isinstance(val, (int, float)): return float(val)
    try:
        return float(str(val).replace('R$', '').replace('.', '').replace(',', '.').strip())
    except: 
        return 0.0

# --- ROTAS ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cpf_form = request.form.get('cpf')
        password_form = request.form.get('password')
        user = User.query.filter_by(cpf=cpf_form).first()
        if user and user.password == password_form:
            login_user(user)
            return redirect(url_for('selecao'))
        flash('CPF ou Senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/selecao')
@login_required
def selecao():
    return render_template('selecao.html', nome=current_user.name)

@app.route('/set_empresa/<empresa_id>')
@login_required
def set_empresa(empresa_id):
    empresas = {'leao': 'Leão Serviços', 'health': 'Health Max'}
    if empresa_id in empresas:
        session['empresa_ativa'] = empresas[empresa_id]
        session['empresa_slug'] = empresa_id
        return redirect(url_for('dashboard'))
    return redirect(url_for('selecao'))

@app.route('/dashboard')
@login_required
def dashboard():
    empresa = session.get('empresa_ativa', 'Grupo L&H')
    return render_template('dashboard.html', empresa=empresa)

@app.route('/receber')
@login_required
def receber():
    empresa = session.get('empresa_ativa')
    slug = session.get('empresa_slug')
    mes_filtro = request.args.get('mes', 'Todos')
    
    query = ContaReceber.query.filter_by(empresa_slug=slug)
    if mes_filtro != 'Todos':
        query = query.filter_by(mes_referencia=mes_filtro)
    
    contas = query.all()
    return render_template('receber.html', 
                           empresa=empresa, 
                           contas=contas,
                           mes_selecionado=mes_filtro)

@app.route('/upload_receber', methods=['POST'])
@login_required
def upload_receber():
    if 'excel_file' not in request.files: return redirect(url_for('receber'))
    file = request.files['excel_file']
    mes_referencia = request.form.get('mes_upload', 'Janeiro')

    if file.filename == '' or not file.filename.endswith(('.xlsx', '.xls')):
        flash('Formato de arquivo inválido.', 'danger')
        return redirect(url_for('receber'))
    
    try:
        df = pd.read_excel(file)
        df.columns = [str(c).strip().upper() for c in df.columns]
        df = df.fillna('')
        slug = session.get('empresa_slug')

        for _, row in df.iterrows():
            nova_conta = ContaReceber(
                empresa_slug=slug,
                mes_referencia=mes_referencia,
                status=str(row.get('STATUS', '')),
                cidade=str(row.get('CIDADE', '')),
                servico=str(row.get('SERVIÇO', row.get('SERVICO', ''))),
                nf=str(row.get('NF', '')),
                empresa_planilha=str(row.get('EMPRESA', '')),
                emissao_nota=str(row.get('EMISSÃO DA NOTA', row.get('EMISSÃO', ''))),
                vencimento=str(row.get('VENCIMENTO', '')),
                valor_nota=to_float(row.get('VALOR NOTA', 0)),
                iss_retido=str(row.get('ISS RETIDO', '')),
                valor_iss=to_float(row.get('VALOR ISS', 0)),
                porcentagem=str(row.get('PORCENTAGEM', '')),
                valor_ir=to_float(row.get('VALOR IR', 0)),
                valor_liquido=to_float(row.get('VALOR LIQUIDO', 0)),
                valor_recebido=to_float(row.get('VALOR RECEBIDO', 0)),
                diferenca=to_float(row.get('DIFERENÇA', row.get('DIFERENCA', 0))),
                data_pg=str(row.get('DATA PG', '')),
                observacoes=str(row.get('OBSERVAÇÕES', row.get('OBS', '')))
            )
            db.session.add(nova_conta)
        
        db.session.commit()
        flash(f'Planilha de {mes_referencia} importada!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro na importação: {e}', 'danger')
            
    return redirect(url_for('receber'))

@app.route('/adicionar_manual', methods=['POST'])
@login_required
def adicionar_manual():
    slug = session.get('empresa_slug')
    try:
        nova_conta = ContaReceber(
            empresa_slug=slug,
            mes_referencia=request.form.get('mes_referencia'),
            status=request.form.get('status'),
            cidade=request.form.get('cidade'),
            servico=request.form.get('servico'),
            nf=request.form.get('nf'),
            empresa_planilha=request.form.get('empresa_planilha'),
            valor_nota=to_float(request.form.get('valor_nota')),
            valor_recebido=to_float(request.form.get('valor_recebido')),
            data_pg=request.form.get('data_pg')
        )
        db.session.add(nova_conta)
        db.session.commit()
        flash('Lançamento manual realizado!', 'success')
    except Exception as e:
        flash(f'Erro no lançamento: {e}', 'danger')
    return redirect(url_for('receber'))

# ROTA ADICIONADA: Deletar registro individual
@app.route('/deletar_receber/<int:id>')
@login_required
def deletar_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    db.session.delete(conta)
    db.session.commit()
    flash('Registro removido com sucesso!', 'info')
    return redirect(url_for('receber'))

@app.route('/limpar_receber')
@login_required
def limpar_receber():
    slug = session.get('empresa_slug')
    ContaReceber.query.filter_by(empresa_slug=slug).delete()
    db.session.commit()
    flash('Todos os dados foram apagados.', 'warning')
    return redirect(url_for('receber'))

# --- INICIALIZAÇÃO ---

def setup_db():
    with app.app_context():
        db.create_all()
        # Conta padrão de teste
        if not User.query.filter_by(cpf="000.000.000-00").first():
            db.session.add(User(name="Nicolas Silva", cpf="000.000.000-00", password="123"))
            db.session.commit()

if __name__ == '__main__':
    setup_db()
    app.run(debug=True)