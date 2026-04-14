import os
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lh_erp_nicolas_2026_secure_v2')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp_lh.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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

class Colaborador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_slug = db.Column(db.String(50))
    nome = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(20), nullable=False)
    tipo_vinculo = db.Column(db.String(20))
    cargo = db.Column(db.String(100))
    unidade = db.Column(db.String(100))
    salario = db.Column(db.Float, default=0.0)
    data_inicio = db.Column(db.String(20))
    status = db.Column(db.String(20), default="ATIVO")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def limpar_moeda(val):
    if pd.isna(val) or val is None or val == '' or str(val).lower() == 'nan': return 0.0
    if isinstance(val, (int, float)): return float(val)
    v_str = str(val).upper().replace('R$', '').replace(' ', '').strip().replace('.', '').replace(',', '.')
    try:
        return float(v_str)
    except:
        return 0.0

def formatar_data(d):
    if pd.isna(d) or d is None or str(d).strip() == '' or str(d).lower() in ['nat', 'nan']: return ""
    if isinstance(d, datetime): return d.strftime('%d/%m/%Y')
    
    d_str = str(d).strip().split(' ')[0]
    if '-' in d_str and len(d_str) == 10:
        try:
            return datetime.strptime(d_str, '%Y-%m-%d').strftime('%d/%m/%Y')
        except:
            pass
    return d_str

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(cpf=request.form.get('cpf')).first()
        if user and user.check_password(request.form.get('password')):
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
    return render_template('selecao.html')

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
    return render_template('dashboard.html', empresa=session.get('empresa_ativa', 'Grupo L&H'))

@app.route('/faturamento')
@login_required
def faturamento():
    return render_template('faturamento.html', empresa=session.get('empresa_ativa'))

@app.route('/rh')
@login_required
def rh():
    colaboradores = Colaborador.query.filter_by(empresa_slug=session.get('empresa_slug')).all()
    ativos = sum(1 for c in colaboradores if c.status == 'ATIVO')
    afastados = sum(1 for c in colaboradores if c.status != 'ATIVO')
    folha_total = sum(c.salario for c in colaboradores)
    return render_template('rh.html', empresa=session.get('empresa_ativa'), colaboradores=colaboradores, ativos=ativos, afastados=afastados, folha_total=f"{folha_total:,.2f}")

@app.route('/rh/admitir', methods=['POST'])
@login_required
def rh_admitir():
    try:
        novo_colaborador = Colaborador(
            empresa_slug=session.get('empresa_slug'),
            nome=request.form.get('nome'),
            documento=request.form.get('documento'),
            tipo_vinculo=request.form.get('tipo_vinculo'),
            cargo=request.form.get('cargo'),
            unidade=request.form.get('unidade'),
            salario=limpar_moeda(request.form.get('salario')),
            data_inicio=formatar_data(request.form.get('data_inicio')),
            status=request.form.get('status', 'ATIVO')
        )
        db.session.add(novo_colaborador)
        db.session.commit()
        flash('Colaborador admitido com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao admitir: {e}', 'danger')
    return redirect(url_for('rh'))

@app.route('/contratos')
@login_required
def contratos():
    return render_template('contratos.html', empresa=session.get('empresa_ativa'))

@app.route('/receber')
@login_required
def receber():
    slug = session.get('empresa_slug')
    mes_filtro = request.args.get('mes', 'Todos')
    query = ContaReceber.query.filter_by(empresa_slug=slug)
    if mes_filtro != 'Todos': query = query.filter_by(mes_referencia=mes_filtro)
    return render_template('receber.html', empresa=session.get('empresa_ativa'), contas=query.order_by(ContaReceber.id.desc()).all(), mes_selecionado=mes_filtro)

@app.route('/upload_receber', methods=['POST'])
@login_required
def upload_receber():
    if 'excel_file' not in request.files: return redirect(url_for('receber'))
    file = request.files['excel_file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Formato inválido.', 'danger')
        return redirect(url_for('receber'))
    
    # Captura qual aba de mês estava selecionada no momento do upload
    mes_upload = request.form.get('mes_upload', 'Todos')
    meses_pt = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    mes_atual = meses_pt[datetime.now().month - 1]

    try:
        df = pd.read_excel(file)
        df.dropna(how='all', inplace=True) # Ignora linhas completamente vazias
        
        # Trata os nomes das colunas
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Dicionário de Mapeamento Ultra Extenso
        mapeamento = { 
            'mes': 'mes_referencia', 'mês': 'mes_referencia', 'mes ref': 'mes_referencia', 'mês ref': 'mes_referencia', 'mes de referencia': 'mes_referencia',
            'status': 'status', 'situação': 'status', 'situacao': 'status',
            'cidade': 'cidade', 'município': 'cidade', 'municipio': 'cidade', 'local': 'cidade',
            'servico': 'servico', 'serviço': 'servico', 'tipo de servico': 'servico', 'tipo de serviço': 'servico', 'descrição': 'servico', 'descricao': 'servico', 'objeto': 'servico',
            'nf': 'nf', 'nota fiscal': 'nf', 'nº nota': 'nf', 'numero da nota': 'nf', 'n.f.': 'nf', 'nota': 'nf',
            'empresa': 'empresa_planilha', 'cliente': 'empresa_planilha', 'empresa/cliente': 'empresa_planilha', 'unidade': 'empresa_planilha',
            'emissao': 'emissao_nota', 'emissão': 'emissao_nota', 'data emissao': 'emissao_nota', 'data emissão': 'emissao_nota', 'data de emissao': 'emissao_nota', 'data de emissão': 'emissao_nota', 'emissão da nota': 'emissao_nota', 'data da emissao': 'emissao_nota', 'data da emissão': 'emissao_nota', 'dt emissao': 'emissao_nota', 'dt emissão': 'emissao_nota',
            'vencimento': 'vencimento', 'data vencimento': 'vencimento', 'data de vencimento': 'vencimento', 'dt vencimento': 'vencimento',
            'valor nota': 'valor_nota', 'bruto': 'valor_nota', 'valor bruto': 'valor_nota', 'valor nf': 'valor_nota',
            'iss retido': 'iss_retido', 'iss retido?': 'iss_retido', 'tem iss': 'iss_retido',
            'valor iss': 'valor_iss', 'iss': 'valor_iss', 'desconto iss': 'valor_iss',
            '%': 'porcentagem', 'porcentagem': 'porcentagem', 'taxa': 'porcentagem', 'aliquota': 'porcentagem', 'alíquota': 'porcentagem',
            'valor ir': 'valor_ir', 'ir': 'valor_ir', 'desconto ir': 'valor_ir', 'irrf': 'valor_ir', 'valor irrf': 'valor_ir',
            'valor liquido': 'valor_liquido', 'líquido': 'valor_liquido', 'liquido': 'valor_liquido', 'valor líquido': 'valor_liquido',
            'valor recebido': 'valor_recebido', 'recebido': 'valor_recebido', 'total recebido': 'valor_recebido',
            'diferenca': 'diferenca', 'diferença': 'diferenca', 'saldo': 'diferenca', 'em aberto': 'diferenca',
            'data pg': 'data_pg', 'pagamento': 'data_pg', 'data pagamento': 'data_pg', 'data de pagamento': 'data_pg', 'dt pagamento': 'data_pg', 'pago em': 'data_pg',
            'obs': 'observacoes', 'observacoes': 'observacoes', 'observações': 'observacoes', 'historico': 'observacoes', 'histórico': 'observacoes'
        }
        df.rename(columns=mapeamento, inplace=True)
        
        # Inteligência de Fallback para colunas problemáticas (Serviço e Emissão)
        for col in df.columns:
            if col not in mapeamento.values():
                if 'emiss' in col:
                    df.rename(columns={col: 'emissao_nota'}, inplace=True)
                elif 'servi' in col:
                    df.rename(columns={col: 'servico'}, inplace=True)
                elif 'vencim' in col:
                    df.rename(columns={col: 'vencimento'}, inplace=True)
                elif 'cidad' in col or 'munic' in col:
                    df.rename(columns={col: 'cidade'}, inplace=True)
        
        for _, row in df.iterrows():
            if pd.isna(row.get('valor_nota')) and pd.isna(row.get('nf')) and pd.isna(row.get('cidade')): continue
            
            v_nota = limpar_moeda(row.get('valor_nota'))
            v_iss = limpar_moeda(row.get('valor_iss'))
            v_ir = limpar_moeda(row.get('valor_ir'))
            v_rec = limpar_moeda(row.get('valor_recebido'))
            v_liq = (v_nota - v_iss - v_ir) if pd.isna(row.get('valor_liquido')) else limpar_moeda(row.get('valor_liquido'))
            v_dif = (v_liq - v_rec) if pd.isna(row.get('diferenca')) else limpar_moeda(row.get('diferenca'))
            
            # Ajuste inteligente do Mês (Prioriza a Aba do sistema sobre a Planilha)
            mes_planilha = row.get('mes_referencia')
            if pd.isna(mes_planilha) or str(mes_planilha).strip() == '' or str(mes_planilha).lower() in ['nan', 'nat', 'none']:
                mes_final = mes_upload if mes_upload != 'Todos' else mes_atual
            else:
                mes_final = str(mes_planilha).strip().capitalize()

            nova_conta = ContaReceber(
                empresa_slug=session.get('empresa_slug'), 
                mes_referencia=mes_final, 
                status=str(row.get('status', 'ABERTO')).upper().replace('NAN', 'ABERTO'), 
                cidade=str(row.get('cidade', '')).replace('nan', ''), 
                servico=str(row.get('servico', '')).replace('nan', ''), 
                nf=str(row.get('nf', '')).replace('.0','').replace('nan', ''), 
                empresa_planilha=str(row.get('empresa_planilha', '')).replace('nan', ''), 
                emissao_nota=formatar_data(row.get('emissao_nota')), 
                vencimento=formatar_data(row.get('vencimento')), 
                valor_nota=v_nota, 
                iss_retido=str(row.get('iss_retido', 'NÃO')).upper().replace('NAN', 'NÃO'), 
                valor_iss=v_iss, 
                porcentagem=str(row.get('porcentagem', '')).replace('nan', ''), 
                valor_ir=v_ir, 
                valor_liquido=v_liq, 
                valor_recebido=v_rec, 
                diferenca=v_dif, 
                data_pg=formatar_data(row.get('data_pg')), 
                observacoes=str(row.get('observacoes', '')).replace('nan', '')
            )
            db.session.add(nova_conta)
        db.session.commit()
        flash('Registros sincronizados e limpos!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar planilha: {e}', 'danger')
    return redirect(url_for('receber', mes=mes_upload))

@app.route('/adicionar_manual', methods=['POST'])
@login_required
def adicionar_manual():
    try:
        v_nota = limpar_moeda(request.form.get('valor_nota'))
        v_iss = limpar_moeda(request.form.get('valor_iss'))
        v_ir = limpar_moeda(request.form.get('valor_ir'))
        v_rec = limpar_moeda(request.form.get('valor_recebido'))
        v_liq = v_nota - v_iss - v_ir
        
        nova_conta = ContaReceber(
            empresa_slug=session.get('empresa_slug'), 
            mes_referencia=request.form.get('mes_referencia'), 
            status=request.form.get('status', '').upper(), 
            cidade=request.form.get('cidade'), 
            servico=request.form.get('servico'), 
            nf=request.form.get('nf'), 
            empresa_planilha=request.form.get('empresa_planilha'), 
            emissao_nota=request.form.get('emissao_nota'), 
            vencimento=request.form.get('vencimento'), 
            valor_nota=v_nota, 
            iss_retido=request.form.get('iss_retido', '').upper(), 
            valor_iss=v_iss, 
            porcentagem=request.form.get('porcentagem'), 
            valor_ir=v_ir, 
            valor_liquido=v_liq, 
            valor_recebido=v_rec, 
            diferenca=v_liq - v_rec, 
            data_pg=request.form.get('data_pg'), 
            observacoes=request.form.get('observacoes')
        )
        db.session.add(nova_conta)
        db.session.commit()
        flash('Lançamento registrado!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {e}', 'danger')
    return redirect(url_for('receber'))

@app.route('/deletar_receber/<int:id>')
@login_required
def deletar_receber(id):
    db.session.delete(ContaReceber.query.get_or_404(id))
    db.session.commit()
    flash('Registro removido!', 'info')
    return redirect(request.referrer or url_for('receber'))

@app.route('/limpar_receber')
@login_required
def limpar_receber():
    slug = session.get('empresa_slug')
    ContaReceber.query.filter_by(empresa_slug=slug).delete()
    db.session.commit()
    flash('Todos os dados foram apagados da base com sucesso!', 'warning')
    return redirect(url_for('receber'))

def setup_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(cpf="000.000.000-00").first():
            user = User(name="Nicolas Silva", cpf="000.000.000-00")
            user.set_password("123")
            db.session.add(user)
            db.session.commit()

if __name__ == '__main__':
    setup_db()
    app.run(debug=True)