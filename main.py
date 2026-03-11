import hashlib
import requests
import os
import threading
import secrets
import json
import time
import webbrowser

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.lang import Builder
from kivy.storage.jsonstore import JsonStore
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.clipboard import Clipboard
from kivy.factory import Factory
from kivy.animation import Animation
from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Rectangle
from kivy.storage.jsonstore import JsonStore

# --- CONFIGURACIÓN ---
NODE_URL = "https://velcoin-vlc-l3uk.onrender.com"
MARKETPLACE_URL = "https://marketplace-node.onrender.com"

# WALLET FUNDADORA (solo esta puede agregar productos)
WALLET_FUNDADORA = "421fe2ca5041d7fcc82f0abb96a7f03080c2e17c"

# Sesión persistente para el marketplace (mantiene cookies de autenticación)
marketplace_session = requests.Session()

def sha256(msg):
    if isinstance(msg, str):
        msg = msg.encode()
    return hashlib.sha256(msg).hexdigest()

def derivar_wallet_oficial(priv_hex):
    try:
        private_key = priv_hex.lower()
        public_key = sha256(private_key)
        address = sha256(public_key)[:40]
        return address, public_key, private_key
    except Exception as e:
        print(f"Error derivando wallet: {e}")
        return None, None, None

def firmar_transaccion_nodo(public_key, sender, destinatario, monto, nonce):
    try:
        payload = f'{sender}{destinatario}{monto}{nonce}'
        pub_key_hash = sha256(public_key)
        signature = sha256(pub_key_hash + payload)
        return signature
    except Exception as e:
        print(f"Error en firma: {e}")
        return None
        
def firmar_challenge(public_key, challenge):
    try:
        pub_key_hash = sha256(public_key)
        signature = sha256(pub_key_hash + challenge)
        return signature
    except Exception as e:
        print(f"Error firmando challenge: {e}")
        return None

# === NUEVAS FUNCIONES PARA HASH DE TRANSACCIONES ===

def calcular_tx_hash_completo(tx):
    """
    Calcula el hash canónico EXACTO como el nodo.
    IMPORTANTE: El nodo excluye el campo 'hash' al calcular.
    """
    try:
        # EXCLUIR siempre el campo 'hash' (igual que el nodo)
        tx_limpio = {}
        
        for campo in sorted(tx.keys()):
            if campo == 'hash':
                continue
            
            valor = tx[campo]
            
            # Normalizar tipos exactamente como el nodo
            if campo == 'amount':
                tx_limpio[campo] = float(valor)
            elif campo in ['nonce', 'timestamp', 'received_at']:
                tx_limpio[campo] = int(valor) if valor else 0
            else:
                tx_limpio[campo] = str(valor) if valor else ""
        
        # JSON con separadores EXACTOS de Python por defecto
        json_str = json.dumps(tx_limpio, sort_keys=True, separators=(', ', ': '))
        return sha256(json_str)
        
    except Exception as e:
        print(f"Error calculando hash: {e}")
        return tx.get('hash', 'ERROR')
        
def calcular_tx_hash_corto(tx_hash_completo):
    """Versión corta para mostrar (primeros 16 caracteres)"""
    return tx_hash_completo[:16] if tx_hash_completo else 'N/A'


def consultar_tx_en_nodo(tx_hash):
    """
    Consulta una transacción específica al nodo para obtener datos oficiales.
    """
    try:
        url = f"{NODE_URL}/tx/{tx_hash}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error consultando TX al nodo: {e}")
        return None


# === FIN NUEVAS FUNCIONES ===

def autenticar_en_marketplace(wallet, pub_key):
    """
    Autentica al usuario en el marketplace y devuelve True si tuvo éxito.
    Usa la sesión global para mantener las cookies.
    """
    try:
        # 1. Solicitar challenge
        r_challenge = marketplace_session.post(
            f"{MARKETPLACE_URL}/auth/challenge",
            json={"wallet": wallet},
            timeout=10
        )
        
        if r_challenge.status_code != 200:
            print(f"Error obteniendo challenge: {r_challenge.status_code}")
            return False
        
        challenge = r_challenge.json().get('challenge')
        if not challenge:
            print("No se recibió challenge")
            return False
        
        # 2. Firmar challenge
        signature = firmar_challenge(pub_key, challenge)
        if not signature:
            print("Error firmando challenge")
            return False
        
        # 3. Verificar firma
        r_verify = marketplace_session.post(
            f"{MARKETPLACE_URL}/auth/verify",
            json={
                "wallet": wallet,
                "public_key": pub_key,
                "signature": signature
            },
            timeout=10
        )
        
        if r_verify.status_code == 200:
            print(f"Autenticación exitosa para {wallet[:16]}...")
            return True
        else:
            print(f"Verificación fallida: {r_verify.status_code} - {r_verify.text}")
            return False
            
    except Exception as e:
        print(f"Error en autenticación: {e}")
        return False

# --- DISEÑO KV ---
KV = """
<TransactionItem@BoxLayout>:
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(55)
    padding: [dp(10), dp(5)]
    canvas.before:
        Color:
            rgba: (1, 1, 1, 0.05)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
    
    BoxLayout:
        orientation: 'vertical'
        Label:
            id: tipo_monto
            text: "0.00 VLC"
            bold: True
            halign: 'left'
            text_size: self.size
            font_size: '14sp'
        Label:
            id: addr_hist
            text: "Dirección..."
            font_size: '10sp'
            color: (0.6, 0.6, 0.6, 1)
            halign: 'left'
            text_size: self.size

<ProductItem@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: dp(120)
    padding: [dp(15), dp(10)]
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: (0.12, 0.13, 0.18, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    
    Label:
        id: prod_title
        text: "Título"
        font_size: '16sp'
        bold: True
        halign: 'left'
        text_size: self.size
        color: (1, 1, 1, 1)
    
    Label:
        id: prod_price
        text: "0 VLC"
        font_size: '14sp'
        halign: 'left'
        text_size: self.size
        color: (0.4, 0.8, 1, 1)
    
    Label:
        id: prod_desc
        text: "Descripción..."
        font_size: '11sp'
        halign: 'left'
        text_size: self.size
        color: (0.7, 0.7, 0.7, 1)
        size_hint_y: None
        height: dp(30)
    
    Button:
        id: btn_buy
        text: "COMPRAR"
        size_hint_y: None
        height: dp(35)
        background_color: (0.1, 0.45, 1, 1)
        font_size: '12sp'

<PurchaseItem@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: dp(100)
    padding: [dp(15), dp(10)]
    spacing: dp(5)
    canvas.before:
        Color:
            rgba: (0.15, 0.18, 0.25, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    
    Label:
        id: purchase_title
        text: "Producto"
        font_size: '16sp'
        bold: True
        halign: 'left'
        text_size: self.size
        color: (1, 1, 1, 1)
    
    Label:
        id: purchase_status
        text: "Estado: Completado"
        font_size: '12sp'
        halign: 'left'
        text_size: self.size
        color: (0.4, 1, 0.4, 1)
    
    BoxLayout:
        size_hint_y: None
        height: dp(35)
        spacing: dp(10)
        Button:
            id: btn_download
            text: "DESCARGAR"
            background_color: (0.2, 0.8, 0.4, 1)
            font_size: '12sp'
        Button:
            id: btn_details
            text: "DETALLES"
            background_color: (0.1, 0.12, 0.2, 1)
            font_size: '12sp'

<MenuButton@Button>:
    size_hint: None, None
    size: dp(50), dp(40)
    background_color: (0, 0, 0, 0)
    
    canvas.before:
        Color:
            rgba: (1, 1, 1, 1)
        Rectangle:
            pos: self.x + dp(10), self.y + dp(28)
            size: self.width - dp(20), dp(3)
        Rectangle:
            pos: self.x + dp(10), self.y + dp(20)
            size: self.width - dp(20), dp(3)
        Rectangle:
            pos: self.x + dp(10), self.y + dp(12)
            size: self.width - dp(20), dp(3)
        Rectangle:
            pos: self.x + dp(10), self.y + dp(4)
            size: self.width - dp(20), dp(3)

<MainScreen>:
    canvas.before:
        Color:
            rgba: (0.05, 0.06, 0.1, 1)
        Rectangle:
            pos: self.pos
            size: self.size
    
    BoxLayout:
        orientation: 'vertical'
        padding: [dp(15), dp(10)]
        spacing: dp(15)

        # Header
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            
            MenuButton:
                on_release: root.abrir_menu_lateral()
            
            Label:
                text: "VelWallet"
                font_size: '40sp'
                bold: True
                text_size: self.size
                halign: 'center'
                valign: 'middle'

        # Balance
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: dp(140)
            padding: dp(20)
            canvas.before:
                Color:
                    rgba: (0.1, 0.45, 1, 1)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(25)]
            
            Label:
                text: "Balance disponible"
                font_size: '13sp'
                color: (1, 1, 1, 0.7)
                text_size: self.size
                halign: 'center'
            Label:
                id: balance_main
                text: "Cargando..."
                font_size: '28sp'
                bold: True
                text_size: self.size
                halign: 'center'
            Label:
                id: wallet_addr_short
                text: "0x000...000"
                font_size: '10sp'
                color: (1, 1, 1, 0.5)
                text_size: self.size
                halign: 'center'

        # Botones principales
        BoxLayout:
            size_hint_y: None
            height: dp(50)
            spacing: dp(10)
            Button:
                text: "MARKETPLACE"
                background_color: (0.2, 0.8, 0.4, 1)
                font_size: '16sp'
                bold: True
                on_release: root.abrir_marketplace()
            Button:
                text: "MIS COMPRAS"
                background_color: (0.8, 0.4, 0.2, 1)
                font_size: '16sp'
                bold: True
                on_release: root.abrir_mis_compras()

        # Acciones Principales
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            spacing: dp(12)
            Button:
                text: "ENVIAR"
                bold: True
                background_color: (0.1, 0.12, 0.2, 1)
                on_release: root.abrir_dialogo_envio()
            Button:
                text: "RECIBIR"
                bold: True
                background_color: (0.1, 0.12, 0.2, 1)
                on_release: root.mostrar_mi_direccion()

        # Historial
        BoxLayout:
            orientation: 'vertical'
            padding: dp(10)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: (1, 1, 1, 0.03)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(20)]
            
            BoxLayout:
                size_hint_y: None
                height: dp(30)
                Label:
                    text: "HISTORIAL DE TRANSACCIONES"
                    font_size: '11sp'
                    bold: True
                    halign: 'left'
                    text_size: self.size
                    valign: 'middle'
                Button:
                    text: "REFRESCAR"
                    size_hint_x: None
                    width: dp(80)
                    font_size: '10sp'
                    background_color: (0,0,0,0)
                    color: (0.1, 0.45, 1, 1)
                    on_release: root.refrescar_y_minar()

            ScrollView:
                BoxLayout:
                    id: history_list
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(5)

        Button:
            text: "Cerrar Sesión"
            size_hint_y: None
            height: dp(40)
            background_color: (0,0,0,0)
            color: (1, 0.3, 0.3, 0.7)
            on_release: root.logout()

<LoginScreen>:
    canvas.before:
        Color:
            rgba: (0.05, 0.06, 0.1, 1)
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(30)
        spacing: dp(20)
        
        Image:
            source: 'logo.png'
            size_hint_y: None
            height: dp(120)
            allow_stretch: True
            keep_ratio: True
        
        Label:
            text: "VelWallet"
            font_size: '32sp'
            bold: True
            size_hint_y: None
            height: dp(50)
            text_size: self.size
            halign: 'center'

        Widget:
            size_hint_y: None
            height: dp(20)

        Button:
            text: "IMPORTAR WALLET"
            size_hint_y: None
            height: dp(55)
            background_color: (0.1, 0.45, 1, 1)
            on_release: root.show_import_dialog()
        
        Button:
            text: "CREAR NUEVA"
            size_hint_y: None
            height: dp(55)
            background_color: (0.1, 0.12, 0.2, 1)
            on_release: root.create_new_wallet()
        Widget:
"""

class MenuLateral(ModalView):
    def __init__(self, main_screen, **kwargs):
        super().__init__(**kwargs)
        self.main_screen = main_screen
        self.size_hint = (None, 1)
        self.width = dp(300)
        self.pos_hint = {'x': -1, 'y': 0}
        self.background_color = (0, 0, 0, 0)
        self.auto_dismiss = False
        self.build_menu()
    
    def build_menu(self):
        layout = BoxLayout(orientation='vertical', size_hint=(1, 1))
        
        with layout.canvas.before:
            Color(0.08, 0.09, 0.14, 1)
            self.rect = Rectangle(pos=layout.pos, size=layout.size)
            layout.bind(pos=self.update_rect, size=self.update_rect)
        
        header = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(15), dp(10)])
        with header.canvas.before:
            Color(0.1, 0.45, 1, 1)
            self.header_rect = Rectangle(pos=header.pos, size=header.size)
            header.bind(pos=self.update_header_rect, size=self.update_header_rect)
        
        header_label = Label(text="MENÚ", font_size='18sp', bold=True, halign='left', 
                           text_size=(header.width - dp(30), None), valign='middle')
        header.bind(width=lambda inst, w: setattr(header_label, 'text_size', (w - dp(30), None)))
        header.add_widget(header_label)
        layout.add_widget(header)
        
        scroll = ScrollView(size_hint=(1, 1))
        menu_content = BoxLayout(orientation='vertical', size_hint_y=None, height=0,
                                padding=[dp(10), dp(10)], spacing=dp(5))
        
        opciones = [
            ("[b]H[/b]   Inicio", self.menu_inicio),
            ("[b]M[/b]   Marketplace", self.menu_marketplace),
            ("[b]C[/b]   Mis Compras", self.menu_mis_compras),
            ("[b]W[/b]   Whitepaper", self.menu_whitepaper),
            ("[b]S[/b]   Soporte", self.menu_soporte),
            ("[b]P[/b]   Perfil", self.menu_perfil),
        ]
        
        for texto, callback in opciones:
            btn = Button(text=texto, markup=True, size_hint_y=None, height=dp(50),
                        background_color=(0.12, 0.13, 0.18, 1), text_size=(dp(260), None),
                        halign='left', valign='middle', font_size='15sp')
            btn.bind(on_release=callback)
            menu_content.add_widget(btn)
            menu_content.height += dp(55)
        
        espacio = Widget(size_hint_y=None, height=dp(20))
        menu_content.add_widget(espacio)
        menu_content.height += dp(20)
        
        btn_cerrar = Button(text="[b]X[/b]   Cerrar Menú", markup=True, size_hint_y=None,
                           height=dp(45), background_color=(0.6, 0.15, 0.15, 1),
                           text_size=(dp(260), None), halign='center', valign='middle')
        btn_cerrar.bind(on_release=self.dismiss)
        menu_content.add_widget(btn_cerrar)
        menu_content.height += dp(50)
        
        scroll.add_widget(menu_content)
        layout.add_widget(scroll)
        self.add_widget(layout)
    
    def update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size
    
    def update_header_rect(self, instance, value):
        self.header_rect.pos = instance.pos
        self.header_rect.size = instance.size
    
    def on_open(self):
        Animation(pos_hint={'x': 0}, duration=0.3, transition='out_cubic').start(self)
    
    def dismiss(self, *args):
        anim = Animation(pos_hint={'x': -1}, duration=0.25, transition='in_cubic')
        anim.bind(on_complete=lambda *x: super(MenuLateral, self).dismiss())
        anim.start(self)
        return True
    
    def menu_inicio(self, *args):
        self.main_screen.menu_inicio()
        self.dismiss()
    
    def menu_marketplace(self, *args):
        self.main_screen.abrir_marketplace()
        self.dismiss()
    
    def menu_mis_compras(self, *args):
        self.main_screen.abrir_mis_compras()
        self.dismiss()
    
    def menu_whitepaper(self, *args):
        self.main_screen.menu_whitepaper()
        self.dismiss()
    
    def menu_soporte(self, *args):
        self.main_screen.menu_soporte()
        self.dismiss()
    
    def menu_perfil(self, *args):
        self.main_screen.menu_perfil()
        self.dismiss()


class MainScreen(Screen):
    popup_envio = None
    popup_cargando = None
    menu_lateral = None
    popup_marketplace = None
    popup_mis_compras = None
    
    # Cache de compras para evitar perderlas entre sesiones
    mis_compras_cache = []
    
    def on_enter(self):
        self.actualizar_todo()

    def actualizar_todo(self):
        store = JsonStore('vlc_secure.json')
        if store.exists('user'):
            addr = store.get('user')['address']
            self.ids.wallet_addr_short.text = f"{addr[:15]}..."
            threading.Thread(target=self.update_info, args=(addr,), daemon=True).start()

    # === FUNCIÓN MODIFICADA ===
    def update_info(self, addr):
        try:
            r_bal = requests.get(f"{NODE_URL}/balance/{addr}", timeout=10).json()
            balance = r_bal.get('balance', 0)

            r_blocks = requests.get(f"{NODE_URL}/blocks", timeout=10).json()
            mis_txs = []
            for bloque in r_blocks:
                txs = bloque.get('transactions', [])
                block_hash = bloque.get('block_hash', '')
                block_index = bloque.get('index', 0)
                timestamp = bloque.get('timestamp', 0)
                
                for tx in txs:
                    if tx.get('from') == addr or tx.get('to') == addr:
                        # Usar hash del nodo si está disponible, sino calcular
                        tx_hash_nodo = tx.get('hash')
                        if not tx_hash_nodo:
                            tx_sin_hash = {k: v for k, v in tx.items() if k != 'hash'}
                            tx_hash_nodo = calcular_tx_hash_completo(tx_sin_hash)
                        
                        mis_txs.append({
                            "remitente": tx.get('from'),
                            "destinatario": tx.get('to'),
                            "monto": tx.get('amount'),
                            "nonce": tx.get('nonce'),
                            "public_key": tx.get('public_key'),
                            "signature": tx.get('signature'),
                            "timestamp": timestamp,
                            "block_index": block_index,
                            "block_hash": block_hash,
                            "tx_hash_completo": tx_hash_nodo,
                            "tx_hash_corto": calcular_tx_hash_corto(tx_hash_nodo)
                        })
            
            # También buscar en mempool
            try:
                r_mempool = requests.get(f"{NODE_URL}/mempool", timeout=10).json()
                for tx in r_mempool:
                    if tx.get('from') == addr or tx.get('to') == addr:
                        tx_hash_nodo = tx.get('hash')
                        if not tx_hash_nodo:
                            tx_sin_hash = {k: v for k, v in tx.items() if k != 'hash'}
                            tx_hash_nodo = calcular_tx_hash_completo(tx_sin_hash)
                        
                        mis_txs.append({
                            "remitente": tx.get('from'),
                            "destinatario": tx.get('to'),
                            "monto": tx.get('amount'),
                            "nonce": tx.get('nonce'),
                            "public_key": tx.get('public_key'),
                            "signature": tx.get('signature'),
                            "timestamp": tx.get('timestamp', int(time.time())),
                            "block_index": None,
                            "block_hash": None,
                            "tx_hash_completo": tx_hash_nodo,
                            "tx_hash_corto": calcular_tx_hash_corto(tx_hash_nodo),
                            "status": "pending"
                        })
            except Exception as e:
                print(f"Error cargando mempool: {e}")
            
            mis_txs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            Clock.schedule_once(lambda dt: self.refresh_ui(balance, mis_txs))
            
        except Exception as e:
            print(f"Error en update_info: {e}")
            Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", "No se pudo conectar al nodo"))

    # === FUNCIÓN MODIFICADA ===
    def refresh_ui(self, bal, history):
        self.ids.balance_main.text = f"{bal:,.2f} VLC"
        self.ids.history_list.clear_widgets()
        store = JsonStore('vlc_secure.json')
        my_addr = store.get('user')['address']

        for tx in history:
            item = Factory.TransactionItem()
            es_envio = tx['remitente'] == my_addr
            monto_formateado = f"{float(tx['monto']):,.2f}"
            
            # Mostrar hash corto en la lista
            item.ids.tipo_monto.text = f"{'-' if es_envio else '+'} {monto_formateado} VLC"
            item.ids.tipo_monto.color = (1, 0.4, 0.4, 1) if es_envio else (0.4, 1, 0.4, 1)
            item.ids.addr_hist.text = f"{tx['tx_hash_corto']}... | {'Para: ' if es_envio else 'De: '}{tx['destinatario' if es_envio else 'remitente'][:12]}..."
            
            # Guardar datos completos para el popup
            item.tx_data = tx
            item.es_envio = es_envio
            
            # Bind para mostrar detalle
            item.bind(on_touch_down=lambda inst, touch, t=tx, e=es_envio: 
                      self.mostrar_detalle_tx(t, e) if inst.collide_point(*touch.pos) else None)
            
            self.ids.history_list.add_widget(item)

    # === FUNCIÓN MODIFICADA - CONSULTA AL NODO ===
    def mostrar_detalle_tx(self, tx, es_envio):
        from datetime import datetime
        import webbrowser
        
        # Obtener hash de la transacción
        tx_hash_completo = tx.get('tx_hash_completo') or tx.get('tx_hash')
        
        # PRIMERO: Intentar consultar al nodo para datos oficiales
        datos_nodo = None
        if tx_hash_completo:
            datos_nodo = consultar_tx_en_nodo(tx_hash_completo)
        
        # USAR datos del nodo si están disponibles, sino usar datos locales
        if datos_nodo:
            # Usar datos oficiales del nodo
            tx_hash_mostrar = datos_nodo.get('tx_hash', tx_hash_completo)
            tx_from = datos_nodo.get('from', tx.get('remitente', 'N/A'))
            tx_to = datos_nodo.get('to', tx.get('destinatario', 'N/A'))
            tx_amount = datos_nodo.get('amount', tx.get('monto', 0))
            tx_nonce = datos_nodo.get('nonce', tx.get('nonce', 'N/A'))
            tx_block = datos_nodo.get('block_index')
            tx_block_hash = datos_nodo.get('block_hash')
            tx_confirmations = datos_nodo.get('confirmations', 0)
            tx_status = datos_nodo.get('status', 'unknown')
            tx_timestamp = datos_nodo.get('timestamp', tx.get('timestamp', 0))
        else:
            # Fallback: usar datos locales
            tx_hash_mostrar = tx_hash_completo
            tx_from = tx.get('remitente', tx.get('from', 'N/A'))
            tx_to = tx.get('destinatario', tx.get('to', 'N/A'))
            tx_amount = tx.get('monto', tx.get('amount', 0))
            tx_nonce = tx.get('nonce', 'N/A')
            tx_block = tx.get('block_index')
            tx_block_hash = tx.get('block_hash')
            tx_confirmations = 0 if tx_block is None else 1
            tx_status = tx.get('status', 'pending' if tx_block is None else 'confirmed')
            tx_timestamp = tx.get('timestamp', 0)
        
        # Construir el popup con los datos
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        tipo = "ENVIADO" if es_envio else "RECIBIDO"
        estado_texto = "✅ CONFIRMADO" if tx_status == 'confirmed' else "⏳ PENDIENTE"
        
        # Formatear timestamp
        try:
            if isinstance(tx_timestamp, (int, float)) and tx_timestamp > 0:
                fecha = datetime.fromtimestamp(tx_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            else:
                fecha = 'N/A'
        except:
            fecha = 'N/A'
        
        # Contenido del popup
        contenido = f"""[b]Tipo:[/b] {tipo}
[b]Estado:[/b] {estado_texto}
[b]Monto:[/b] {float(tx_amount):.2f} VLC

[b]Hash Transacción:[/b]
{tx_hash_mostrar}

[b]De:[/b]
{tx_from}

[b]Para:[/b]
{tx_to}

[b]Nonce:[/b] {tx_nonce}
[b]Timestamp:[/b] {fecha}
"""
        
        # Añadir datos de bloque si existen
        if tx_block is not None:
            contenido += f"""
[b]Bloque:[/b] #{tx_block}
[b]Confirmaciones:[/b] {tx_confirmations}
"""
            if tx_block_hash:
                contenido += f"[b]Block Hash:[/b]\n{tx_block_hash}\n"
        
        # Scroll con el contenido
        scroll = ScrollView(size_hint=(1, 1))
        label = Label(
            text=contenido, 
            markup=True, 
            font_size='12sp', 
            halign='left', 
            valign='top',
            size_hint_y=None, 
            text_size=(self.width * 0.75, None)
        )
        label.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
        scroll.add_widget(label)
        layout.add_widget(scroll)
        
        # Botones
        box_botones = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        
        btn_explorer = Button(
            text="VER EN EXPLORER",
            background_color=(0.1, 0.45, 1, 1),
            font_size='10sp'
        )
        
        btn_copiar = Button(
            text="COPIAR HASH",
            background_color=(0.1, 0.8, 0.3, 1),
            font_size='10sp'
        )
        
        btn_cerrar = Button(
            text="CERRAR",
            background_color=(0.6, 0.15, 0.15, 1),
            font_size='10sp'
        )
        
        box_botones.add_widget(btn_explorer)
        box_botones.add_widget(btn_copiar)
        box_botones.add_widget(btn_cerrar)
        layout.add_widget(box_botones)
        
        pop = Popup(
            title=f"Tx: {tx_hash_mostrar[:16]}...", 
            content=layout, 
            size_hint=(0.95, 0.85)
        )
        
        def abrir_explorer(instance):
            # Abrir la transacción específica en el explorer
            url = f"{NODE_URL}/explorer/tx/{tx_hash_mostrar}"
            print(f"Abriendo explorer: {url}")
            webbrowser.open(url)
            self.mostrar_notificacion("Explorador", "Abriendo transacción en explorer")
        
        def copiar_hash(instance):
            Clipboard.copy(tx_hash_mostrar)
            notif = Popup(
                title="Copiado", 
                content=Label(text="Hash copiado al portapapeles"), 
                size_hint=(0.6, None), 
                height=dp(150)
            )
            notif.open()
            Clock.schedule_once(lambda dt: notif.dismiss(), 1.5)
        
        btn_explorer.bind(on_release=abrir_explorer)
        btn_copiar.bind(on_release=copiar_hash)
        btn_cerrar.bind(on_release=pop.dismiss)
        
        pop.open()

    # ==================== MARKETPLACE ====================
    
    def abrir_marketplace(self):
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        header = BoxLayout(size_hint_y=None, height=dp(50))
        header.add_widget(Label(text="MARKETPLACE", font_size='20sp', bold=True))
        layout.add_widget(header)
        
        store = JsonStore('vlc_secure.json')
        my_addr = store.get('user')['address']
        
        if my_addr == WALLET_FUNDADORA:
            btn_agregar = Button(
                text="+ AGREGAR PRODUCTO",
                size_hint_y=None,
                height=dp(45),
                background_color=(0.2, 0.8, 0.4, 1),
                font_size='14sp',
                bold=True
            )
            btn_agregar.bind(on_release=lambda x: self.mostrar_formulario_producto())
            layout.add_widget(btn_agregar)
        
        scroll = ScrollView(size_hint=(1, 1))
        self.products_list = BoxLayout(orientation='vertical', size_hint_y=None, height=0, spacing=dp(10))
        scroll.add_widget(self.products_list)
        layout.add_widget(scroll)
        
        btn_cerrar = Button(text="CERRAR", size_hint_y=None, height=dp(45), background_color=(0.6, 0.15, 0.15, 1))
        layout.add_widget(btn_cerrar)
        
        self.popup_marketplace = Popup(title="", content=layout, size_hint=(0.95, 0.9))
        btn_cerrar.bind(on_release=self.popup_marketplace.dismiss)
        
        threading.Thread(target=self.cargar_productos, daemon=True).start()
        self.popup_marketplace.open()
    
    def cargar_productos(self):
        try:
            r = requests.get(f"{MARKETPLACE_URL}/products", timeout=10)
            productos = r.json()
            Clock.schedule_once(lambda dt: self.mostrar_productos(productos))
        except Exception as e:
            print(f"Error cargando productos: {e}")
            Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", "No se pudieron cargar los productos"))
    
    def mostrar_productos(self, productos):
        self.products_list.clear_widgets()
        self.products_list.height = 0
        
        for prod in productos:
            item = Factory.ProductItem()
            item.ids.prod_title.text = prod.get('title', 'Sin título')
            item.ids.prod_price.text = f"{prod.get('price', 0)} VLC"
            item.ids.prod_desc.text = prod.get('description', '')[:50] + '...'
            item.ids.btn_buy.bind(on_release=lambda x, p=prod: self.comprar_producto(p))
            self.products_list.add_widget(item)
            self.products_list.height += dp(130)
        
        if not productos:
            label = Label(text="No hay productos disponibles", font_size='14sp', color=(0.5, 0.5, 0.5, 1))
            self.products_list.add_widget(label)
            self.products_list.height = dp(50)
    
    def mostrar_formulario_producto(self):
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        titulo = TextInput(hint_text="Título del producto", size_hint_y=None, height=dp(45))
        descripcion = TextInput(hint_text="Descripción", multiline=True, size_hint_y=None, height=dp(80))
        precio = TextInput(hint_text="Precio en VLC", input_filter='float', size_hint_y=None, height=dp(45))
        categoria = TextInput(hint_text="Categoría", size_hint_y=None, height=dp(45))
        github_repo = TextInput(hint_text="Repo GitHub (ej: usuario/repo)", size_hint_y=None, height=dp(45))
        github_path = TextInput(hint_text="Nombre exacto del producto en el repo", size_hint_y=None, height=dp(45))
        
        layout.add_widget(Label(text="NUEVO PRODUCTO", font_size='18sp', bold=True, size_hint_y=None, height=dp(30)))
        layout.add_widget(titulo)
        layout.add_widget(descripcion)
        layout.add_widget(precio)
        layout.add_widget(categoria)
        layout.add_widget(Label(text="Configuración GitHub:", font_size='12sp', color=(0.7, 0.7, 0.7, 1), size_hint_y=None, height=dp(25)))
        layout.add_widget(github_repo)
        layout.add_widget(github_path)
        
        btn_guardar = Button(text="GUARDAR PRODUCTO", size_hint_y=None, height=dp(50), background_color=(0.2, 0.8, 0.4, 1))
        layout.add_widget(btn_guardar)
        
        btn_cancelar = Button(text="CANCELAR", size_hint_y=None, height=dp(45), background_color=(0.6, 0.15, 0.15, 1))
        layout.add_widget(btn_cancelar)
        
        pop = Popup(title="", content=layout, size_hint=(0.9, None), height=dp(550))
        btn_cancelar.bind(on_release=pop.dismiss)
        
        def guardar(instance):
            if not all([titulo.text, descripcion.text, precio.text]):
                self.mostrar_notificacion("Error", "Completa todos los campos obligatorios")
                return
            
            try:
                price = float(precio.text)
            except:
                self.mostrar_notificacion("Error", "Precio inválido")
                return
            
            self.autenticar_y_crear_producto({
                "title": titulo.text,
                "description": descripcion.text,
                "price_vlc": price,
                "category": categoria.text or "General",
                "type": "github_private" if github_repo.text else "digital",
                "download_url": "",
                "github_repo": github_repo.text,
                "github_path": github_path.text
            }, pop)
        
        btn_guardar.bind(on_release=guardar)
        pop.open()
    
    def autenticar_y_crear_producto(self, producto_data, popup_formulario):
        store = JsonStore('vlc_secure.json').get('user')
        wallet = store['address']
        pub_key = store['pub']
        
        def auth_and_create():
            if autenticar_en_marketplace(wallet, pub_key):
                try:
                    r_create = marketplace_session.post(
                        f"{MARKETPLACE_URL}/products",
                        json=producto_data,
                        timeout=10
                    )
                    
                    if r_create.status_code == 200:
                        Clock.schedule_once(lambda dt: popup_formulario.dismiss(), 0)
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion("Éxito", "Producto creado correctamente"), 0)
                        Clock.schedule_once(lambda dt: self.cargar_productos(), 0)
                    else:
                        error = r_create.json().get('error', 'Error desconocido')
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"No se pudo crear: {error}"), 0)
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Error de conexión: {str(e)}"), 0)
            else:
                Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", "Autenticación fallida"), 0)
        
        threading.Thread(target=auth_and_create, daemon=True).start()
    
    def comprar_producto(self, producto):
        product_id = producto.get('id')
        precio = producto.get('price', 0)
        
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        layout.add_widget(Label(text=f"¿Comprar '{producto.get('title')}'?", font_size='16sp', bold=True))
        layout.add_widget(Label(text=f"Precio: {precio} VLC", font_size='14sp', color=(0.4, 0.8, 1, 1)))
        
        btn_confirmar = Button(text="CONFIRMAR COMPRA", size_hint_y=None, height=dp(50), background_color=(0.2, 0.8, 0.4, 1))
        btn_cancelar = Button(text="CANCELAR", size_hint_y=None, height=dp(45), background_color=(0.6, 0.15, 0.15, 1))
        
        layout.add_widget(btn_confirmar)
        layout.add_widget(btn_cancelar)
        
        pop = Popup(title="Confirmar Compra", content=layout, size_hint=(0.9, None), height=dp(280))
        btn_cancelar.bind(on_release=pop.dismiss)
        
        def confirmar_compra(instance):
            pop.dismiss()
            self.procesar_compra(product_id, precio, producto)
        
        btn_confirmar.bind(on_release=confirmar_compra)
        pop.open()
    
    # ==================== CORRECCIÓN CRÍTICA AQUÍ ====================
    def procesar_compra(self, product_id, precio, producto_info=None):
        """
        CORREGIDO: Verifica en el blockchain si ya existe un pago para este producto
        ANTES de enviar dinero. Usa el endpoint /check_purchase del marketplace.
        """
        store = JsonStore('vlc_secure.json').get('user')
        my_addr = store['address']
        pub_key = store['pub']
        
        # ========== PASO 1: AUTENTICACIÓN ==========
        self.mostrar_popup_cargando("Verificando...")
        
        def proceso_completo():
            try:
                # Verificar autenticación
                if not autenticar_en_marketplace(my_addr, pub_key):
                    Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", "Autenticación fallida"), 0)
                    return
                
                # ========== PASO 2: VERIFICAR SI YA COMPRÓ ESTE PRODUCTO ==========
                Clock.schedule_once(lambda dt: self.mostrar_popup_cargando("Verificando compras..."), 0)
                
                try:
                    # Usar el endpoint /check_purchase del marketplace
                    r_check = marketplace_session.get(
                        f"{MARKETPLACE_URL}/check_purchase/{product_id}",
                        timeout=10
                    )
                    
                    if r_check.status_code == 200:
                        resultado = r_check.json()
                        if resultado.get('purchased'):
                            Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                            Clock.schedule_once(lambda dt: self.mostrar_notificacion(
                                "Info", 
                                "Ya tienes este producto. Ve a 'Mis Compras' para descargarlo."
                            ), 0)
                            return
                    
                    # Si el endpoint no existe o falla, verificar en el blockchain localmente
                    # Buscar transacciones anteriores a WALLET_FUNDADORA con el mismo monto
                    try:
                        r_blocks = requests.get(f"{NODE_URL}/blocks", timeout=10).json()
                        for bloque in r_blocks:
                            for tx in bloque.get('transactions', []):
                                # Si ya envió dinero a la wallet fundadora con el mismo monto
                                if (tx.get('from') == my_addr and 
                                    tx.get('to') == WALLET_FUNDADORA and
                                    abs(float(tx.get('amount', 0)) - precio) < 0.01):
                                    
                                    # Verificar si es para este producto consultando si puede descargar
                                    try:
                                        r_download_check = marketplace_session.get(
                                            f"{MARKETPLACE_URL}/download/{product_id}",
                                            timeout=5
                                        )
                                        if r_download_check.status_code == 200:
                                            Clock.schedule_once(lambda dt:                       self.cerrar_popup_cargando(), 0)
                                            Clock.schedule_once(lambda dt: self.mostrar_notificacion(
                                                "Info", 
                                                "Ya tienes este producto. Ve a 'Mis Compras' para descargarlo."
                                            ), 0)
                                            return
                                    except:
                                        pass
                    except Exception as e:
                        print(f"Error verificando blockchain: {e}")
                        # Continuar de todas formas, el /buy fallará si ya existe
                        
                except Exception as e:
                    print(f"Error verificando compra previa: {e}")
                    # Continuar, el /buy del marketplace tiene su propia validación
                
                # ========== PASO 3: INTENTAR REGISTRAR COMPRA EN MARKETPLACE PRIMERO ==========
                # Esto es la clave: el marketplace tiene una transacción atómica
                # Si falla aquí, NO se ha enviado dinero todavía
                
                Clock.schedule_once(lambda dt: self.mostrar_popup_cargando("Reservando producto..."), 0)
                
                try:
                    # Intentar crear la compra en el marketplace SIN enviar pago aún
                    # El endpoint /buy del marketplace verifica si ya existe y crea el registro
                    r_reserve = marketplace_session.post(
                        f"{MARKETPLACE_URL}/buy",
                        json={"product_id": product_id},
                        timeout=10
                    )
                    
                    if r_reserve.status_code == 400 and 'already purchased' in r_reserve.text.lower():
                        Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion(
                            "Info", 
                            "Ya tienes este producto. Ve a 'Mis Compras' para descargarlo."
                        ), 0)
                        return
                    
                    if r_reserve.status_code != 200:
                        error = r_reserve.json().get('error', 'Error desconocido')
                        Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion(
                            "Error", 
                            f"No se pudo reservar el producto: {error}"
                        ), 0)
                        return
                    
                    # La compra se reservó exitosamente en el marketplace
                    # Ahora SÍ enviamos el pago
                    tx_hash_reservado = r_reserve.json().get('tx_hash')
                    
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion(
                        "Error", 
                        f"Error conectando con marketplace: {str(e)}"
                    ), 0)
                    return
                
                # ========== PASO 4: VERIFICAR BALANCE ==========
                Clock.schedule_once(lambda dt: self.mostrar_popup_cargando("Verificando balance..."), 0)
                
                try:
                    r_bal = requests.get(f"{NODE_URL}/balance/{my_addr}", timeout=10).json()
                    balance = r_bal.get('balance', 0)
                    
                    if balance < precio:
                        Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion(
                            "Error", 
                            f"Balance insuficiente. Tienes {balance} VLC, necesitas {precio} VLC"
                        ), 0)
                        return
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"No se pudo verificar balance: {str(e)}"), 0)
                    return
                
                # ========== PASO 5: PREPARAR Y ENVIAR TRANSACCIÓN ==========
                nonce = int(time.time() * 1000)
                firma = firmar_transaccion_nodo(pub_key, my_addr, WALLET_FUNDADORA, precio, nonce)
                
                if not firma:
                    Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", "No se pudo firmar la transacción"), 0)
                    return
                
                payload_tx = {
                    "from": my_addr,
                    "to": WALLET_FUNDADORA,
                    "amount": precio,
                    "nonce": nonce,
                    "public_key": pub_key,
                    "signature": firma
                }
                
                Clock.schedule_once(lambda dt: self.mostrar_popup_cargando("Enviando pago..."), 0)
                
                try:
                    r_send = requests.post(f"{NODE_URL}/send", json=payload_tx, timeout=10)
                    resp_send = r_send.json()
                    
                    if not resp_send.get('accepted'):
                        Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                        error = resp_send.get('error', 'Error desconocido')
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Pago rechazado: {error}"), 0)
                        return
                    
                    tx_hash = resp_send.get('tx_hash') or calcular_tx_hash_completo(payload_tx)
                    
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Error enviando pago: {str(e)}"), 0)
                    return
                
                # ========== PASO 6: MINAR BLOQUE ==========
                Clock.schedule_once(lambda dt: self.mostrar_popup_cargando("Confirmando transacción..."), 0)
                
                try:
                    requests.post(f"{NODE_URL}/mine", json={}, timeout=30)
                except Exception as e:
                    print(f"Error minando (continuando): {e}")
                
                # ========== PASO 7: ÉXITO ==========
                Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                
                # Guardar en caché local
                if producto_info:
                    compra_data = {
                        'product_id': product_id,
                        'title': producto_info.get('title', 'Producto'),
                        'price': precio,
                        'status': 'completed',
                        'timestamp': int(time.time()),
                        'tx_hash': tx_hash
                    }
                    existe = any(c['product_id'] == product_id for c in self.mis_compras_cache)
                    if not existe:
                        self.mis_compras_cache.append(compra_data)
                
                Clock.schedule_once(lambda dt: self.mostrar_notificacion(
                    "Éxito", 
                    "¡Compra exitosa! Ve a 'Mis Compras' para descargar."
                ), 0)
                Clock.schedule_once(lambda dt: self.actualizar_todo(), 0)
                    
            except Exception as e:
                print(f"Error general en proceso_compra: {e}")
                Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Error inesperado: {str(e)}"), 0)
        
        threading.Thread(target=proceso_completo, daemon=True).start()

    # ==================== MIS COMPRAS ====================
    
    def abrir_mis_compras(self):
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        header = BoxLayout(size_hint_y=None, height=dp(50))
        header.add_widget(Label(text="MIS COMPRAS", font_size='20sp', bold=True))
        layout.add_widget(header)
        
        scroll = ScrollView(size_hint=(1, 1))
        self.purchases_list = BoxLayout(orientation='vertical', size_hint_y=None, height=0, spacing=dp(10))
        scroll.add_widget(self.purchases_list)
        layout.add_widget(scroll)
        
        btn_cerrar = Button(text="CERRAR", size_hint_y=None, height=dp(45), background_color=(0.6, 0.15, 0.15, 1))
        layout.add_widget(btn_cerrar)
        
        self.popup_mis_compras = Popup(title="", content=layout, size_hint=(0.95, 0.9))
        btn_cerrar.bind(on_release=self.popup_mis_compras.dismiss)
        
        threading.Thread(target=self.cargar_mis_compras, daemon=True).start()
        self.popup_mis_compras.open()
    
    def cargar_mis_compras(self):
        store = JsonStore('vlc_secure.json').get('user')
        my_addr = store['address']
        pub_key = store['pub']
        
        def auth_and_load():
            # Primero mostrar compras en caché
            compras = list(self.mis_compras_cache)
            
            if not autenticar_en_marketplace(my_addr, pub_key):
                # Si falla auth, mostrar al menos las compras en caché
                Clock.schedule_once(lambda dt: self.mostrar_mis_compras(compras))
                return
            
            try:
                # Obtener productos del marketplace
                r_products = marketplace_session.get(f"{MARKETPLACE_URL}/products", timeout=10)
                products = {p['id']: p for p in r_products.json()}
                
                # Buscar en el historial de transacciones pagos al marketplace
                try:
                    r_blocks = requests.get(f"{NODE_URL}/blocks", timeout=10).json()
                    for bloque in r_blocks:
                        for tx in bloque.get('transactions', []):
                            # Si enviaste dinero a la wallet fundadora, es una compra
                            if tx.get('from') == my_addr and tx.get('to') == WALLET_FUNDADORA:
                                monto = float(tx.get('amount', 0))
                                # Buscar producto con ese precio
                                for prod_id, product in products.items():
                                    if abs(product.get('price', 0) - monto) < 0.01:
                                        # Verificar si ya está en la lista
                                        existe = False
                                        for c in compras:
                                            if c['product_id'] == prod_id:
                                                existe = True
                                                break
                                        if not existe:
                                            compras.append({
                                                'product_id': prod_id,
                                                'title': product.get('title', 'Producto'),
                                                'price': product.get('price', 0),
                                                'status': 'completed'
                                            })
                except Exception as e:
                    print(f"Error buscando en historial: {e}")
                
                # Intentar verificar descargas (sin consumir intentos)
                # Solo verificamos el status, no descargamos
                for prod_id in list(products.keys()):
                    try:
                        r_check = marketplace_session.get(
                            f"{MARKETPLACE_URL}/download/{prod_id}",
                            timeout=3
                        )
                        if r_check.status_code == 200:
                            # Tiene acceso de descarga, agregar si no está
                            existe = False
                            for c in compras:
                                if c['product_id'] == prod_id:
                                    existe = True
                                    break
                            if not existe:
                                product = products[prod_id]
                                compras.append({
                                    'product_id': prod_id,
                                    'title': product.get('title', 'Producto'),
                                    'price': product.get('price', 0),
                                    'status': 'completed'
                                })
                    except:
                        pass
                
                Clock.schedule_once(lambda dt: self.mostrar_mis_compras(compras))
                
            except Exception as e:
                print(f"Error cargando compras: {e}")
                # Mostrar al menos las compras en caché
                Clock.schedule_once(lambda dt: self.mostrar_mis_compras(compras))
        
        threading.Thread(target=auth_and_load, daemon=True).start()
    
    def mostrar_mis_compras(self, compras):
        self.purchases_list.clear_widgets()
        self.purchases_list.height = 0
        
        if not compras:
            label = Label(
                text="No tienes compras aún\nVe al Marketplace para comprar productos",
                font_size='14sp',
                color=(0.5, 0.5, 0.5, 1),
                halign='center'
            )
            self.purchases_list.add_widget(label)
            self.purchases_list.height = dp(100)
            return
        
        for compra in compras:
            item = Factory.PurchaseItem()
            item.ids.purchase_title.text = compra['title']
            item.ids.purchase_status.text = f"Estado: {compra['status'].upper()}"
            
            prod_id = compra['product_id']
            item.ids.btn_download.bind(on_release=lambda x, pid=prod_id: self.descargar_producto(pid))
            item.ids.btn_details.bind(on_release=lambda x, c=compra: self.mostrar_detalle_compra(c))
            
            self.purchases_list.add_widget(item)
            self.purchases_list.height += dp(110)
    
    def descargar_producto(self, product_id):
        """
        SOLUCIÓN: Genera una URL de descarga con token temporal firmado.
        El servidor debe modificar su endpoint /download para aceptar estos parámetros.
        """
        store = JsonStore('vlc_secure.json')
        user_data = store.get('user')
        my_addr = user_data['address']
        pub_key = user_data['pub']
        
        # Generar token temporal (válido por 30 minutos)
        expira_en = 30 * 60  # 30 minutos en segundos
        timestamp_expiracion = int(time.time()) + expira_en
        
        # Crear firma de autorización usando pub_key (NO priv_key)
        # wallet + product_id + expiración
        mensaje = f"{my_addr}:{product_id}:{timestamp_expiracion}"
        firma = sha256(sha256(pub_key) + mensaje)
        
        # Construir URL con parámetros de autenticación
        from urllib.parse import urlencode
        params = {
            'wallet': my_addr,
            'pubkey': pub_key,
            'expires': timestamp_expiracion,
            'signature': firma
        }
        query_string = urlencode(params)
        download_url = f"{MARKETPLACE_URL}/download/{product_id}?{query_string}"
        
        print(f"Abriendo navegador con URL: {download_url[:100]}...")
        
        # Abrir navegador
        webbrowser.open(download_url)
        
        # Notificar al usuario
        self.mostrar_notificacion(
            "Descarga Iniciada",
            "Se abrió tu navegador para descargar el archivo.\n\nEl enlace es válido por 30 minutos."
        )
    
    def mostrar_detalle_compra(self, compra):
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        contenido = f"""
[b]Producto:[/b] {compra['title']}
[b]Precio:[/b] {compra['price']} VLC
[b]Estado:[/b] {compra['status'].upper()}
[b]ID:[/b] {compra['product_id'][:16]}...
        """
        
        label = Label(
            text=contenido,
            markup=True,
            font_size='14sp',
            halign='left',
            valign='top',
            size_hint_y=None,
            text_size=(dp(220), None)
        )
        label.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
        
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(label)
        layout.add_widget(scroll)
        
        btn_cerrar = Button(
            text="CERRAR",
            size_hint_y=None,
            height=dp(45),
            background_color=(0.1, 0.45, 1, 1)
        )
        layout.add_widget(btn_cerrar)
        
        pop = Popup(
            title="Detalle de Compra",
            content=layout,
            size_hint=(0.9, None),
            height=dp(350)
        )
        btn_cerrar.bind(on_release=pop.dismiss)
        pop.open()

    def abrir_dialogo_envio(self):
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        dest = TextInput(hint_text="Dirección destino", multiline=False, size_hint_y=None, height=dp(45))
        cant = TextInput(hint_text="Monto", input_filter='float', multiline=False, size_hint_y=None, height=dp(45))
        btn = Button(text="ENVIAR AHORA", background_color=(0.1, 0.45, 1, 1), size_hint_y=None, height=dp(50))
        
        layout.add_widget(dest)
        layout.add_widget(cant)
        layout.add_widget(btn)
        
        self.popup_envio = Popup(title="Enviar VelCoin", content=layout, size_hint=(0.9, None), height=dp(280))

        def confirmar(instance):
            store = JsonStore('vlc_secure.json').get('user')
            monto_str = cant.text.strip()
            destino = dest.text.strip()
            
            if not monto_str or not destino:
                self.mostrar_notificacion("Error", "Completa todos los campos")
                return
            
            try:
                monto = float(monto_str)
                if monto <= 0:
                    raise ValueError
            except:
                self.mostrar_notificacion("Error", "Monto inválido")
                return
            
            nonce = int(time.time() * 1000)
            firma = firmar_transaccion_nodo(store['pub'], store['address'], destino, monto, nonce)
            
            if not firma:
                self.mostrar_notificacion("Error", "No se pudo firmar la transacción")
                return
            
            payload = {
                "from": store['address'],
                "to": destino,
                "amount": monto,
                "nonce": nonce,
                "public_key": store['pub'],
                "signature": firma
            }
            
            self.mostrar_popup_cargando("Enviando transacción...")
            
            def enviar_y_minar():
                try:
                    r = requests.post(f"{NODE_URL}/send", json=payload, timeout=10)
                    respuesta = r.json()
                    
                    if not respuesta.get('accepted'):
                        Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                        error = respuesta.get('error', 'Error desconocido')
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Transacción rechazada: {error}"), 0)
                        Clock.schedule_once(lambda dt: self.cerrar_popup_envio(), 0)
                        return
                    
                    Clock.schedule_once(lambda dt: self.mostrar_popup_cargando("Minando bloque..."), 0)
                    r_mine = requests.post(f"{NODE_URL}/mine", json={}, timeout=30)
                    
                    if r_mine.status_code == 200:
                        resultado = r_mine.json()
                        if resultado.get('success'):
                            Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                            Clock.schedule_once(lambda dt: self.cerrar_popup_envio(), 0)
                            Clock.schedule_once(lambda dt: self.actualizar_todo(), 0)
                            Clock.schedule_once(lambda dt: self.mostrar_notificacion("Éxito", f"¡Transacción confirmada! Bloque #{resultado['block']['index']}"), 0)
                        else:
                            Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                            Clock.schedule_once(lambda dt: self.cerrar_popup_envio(), 0)
                            Clock.schedule_once(lambda dt: self.actualizar_todo(), 0)
                            Clock.schedule_once(lambda dt: self.mostrar_notificacion("Advertencia", "Transacción enviada pero el minado falló. Presiona REFRESCAR."), 0)
                    else:
                        Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                        Clock.schedule_once(lambda dt: self.cerrar_popup_envio(), 0)
                        Clock.schedule_once(lambda dt: self.actualizar_todo(), 0)
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion("Advertencia", "Transacción enviada pero el minado falló. Presiona REFRESCAR."), 0)
                        
                except Exception as err:
                    print(f"Error en enviar_y_minar: {err}")
                    Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Fallo de conexión: {str(err)}"), 0)
                    Clock.schedule_once(lambda dt: self.cerrar_popup_envio(), 0)
            
            threading.Thread(target=enviar_y_minar, daemon=True).start()

        btn.bind(on_release=confirmar)
        self.popup_envio.open()

    def mostrar_popup_cargando(self, mensaje="Cargando..."):
        self.cerrar_popup_cargando()
        content = BoxLayout(orientation='vertical', padding=dp(20))
        label = Label(text=mensaje, font_size='14sp', halign='center', valign='middle')
        content.add_widget(label)
        self.popup_cargando = Popup(title="Procesando", content=content, size_hint=(0.8, None), height=dp(180), auto_dismiss=False)
        self.popup_cargando.open()
    
    def cerrar_popup_cargando(self):
        if self.popup_cargando:
            self.popup_cargando.dismiss()
            self.popup_cargando = None
    
    def cerrar_popup_envio(self):
        if self.popup_envio:
            self.popup_envio.dismiss()
            self.popup_envio = None

    def refrescar_y_minar(self):
        self.mostrar_popup_cargando("Verificando mempool...")
        
        def verificar_y_minar():
            try:
                r_mempool = requests.get(f"{NODE_URL}/mempool", timeout=10)
                mempool = r_mempool.json()
                
                if len(mempool) == 0:
                    Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                    Clock.schedule_once(lambda dt: self.actualizar_todo(), 0)
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Info", "No hay transacciones pendientes"), 0)
                    return
                
                Clock.schedule_once(lambda dt: self.mostrar_popup_cargando("Minando bloque..."), 0)
                r_mine = requests.post(f"{NODE_URL}/mine", json={}, headers={"Content-Type": "application/json"}, timeout=30)
                
                if r_mine.status_code == 200:
                    resultado = r_mine.json()
                    if resultado.get('success'):
                        Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                        Clock.schedule_once(lambda dt: self.actualizar_todo(), 0)
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion("Éxito", f"Bloque minado! #{resultado['block']['index']}"), 0)
                    else:
                        Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", "El minado no tuvo éxito"), 0)
                else:
                    Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", "Error al minar"), 0)
            except Exception as err:
                Clock.schedule_once(lambda dt: self.cerrar_popup_cargando(), 0)
                Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Error de conexión: {str(err)}"), 0)
        
        threading.Thread(target=verificar_y_minar, daemon=True).start()


    def mostrar_mi_direccion(self):
        addr = JsonStore('vlc_secure.json').get('user')['address']
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        txt = TextInput(text=addr, readonly=True, size_hint_y=None, height=dp(50), font_size='12sp', halign='center')
        btn = Button(text="COPIAR AL PORTAPAPELES", background_color=(0.1, 0.8, 0.3, 1), size_hint_y=None, height=dp(50))
        layout.add_widget(txt)
        layout.add_widget(btn)
        pop = Popup(title="Tu Dirección", content=layout, size_hint=(0.9, None), height=dp(250))
        btn.bind(on_release=lambda x: [Clipboard.copy(addr), pop.dismiss()])
        pop.open()

    def mostrar_notificacion(self, titulo, mensaje):
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        label = Label(text=mensaje, font_size='14sp', halign='center', valign='middle', size_hint_y=None, text_size=(self.width * 0.65, None), markup=True)
        label.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll.add_widget(label)
        layout.add_widget(scroll)
        btn_ok = Button(text="OK", size_hint_y=None, height=dp(45), background_color=(0.1, 0.45, 1, 1))
        layout.add_widget(btn_ok)
        pop = Popup(title=titulo, content=layout, size_hint=(0.85, None), height=dp(280), auto_dismiss=False)
        btn_ok.bind(on_release=pop.dismiss)
        pop.open()

    def abrir_menu_lateral(self):
        if self.menu_lateral is None:
            self.menu_lateral = MenuLateral(main_screen=self)
        self.menu_lateral.open()
    
    def menu_inicio(self):
        self.actualizar_todo()
    
    def menu_whitepaper(self):
        import webbrowser
        webbrowser.open("https://velcoin-vlc.onrender.com")
    
    def menu_soporte(self):
        import webbrowser
        webbrowser.open("https://wa.me/13156961731")
        self.mostrar_notificacion("Portal de Soporte", "Abriendo WhatsApp...")
    
    def menu_perfil(self):
        self.mostrar_notificacion("Perfil", "Disponible próximamente")

    def logout(self):
        if os.path.exists('vlc_secure.json'): os.remove('vlc_secure.json')
        self.manager.current = 'login'


class LoginScreen(Screen):
    def create_new_wallet(self):
        new_priv = ''.join(secrets.choice('0123456789abcdef') for _ in range(64))
        addr, pub, priv_norm = derivar_wallet_oficial(new_priv)
        
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        lbl_titulo = Label(text="GUARDA ESTA CLAVE (NO LA PIERDAS):", color=(1,0.8,0,1), font_size='14sp', halign='center')
        content.add_widget(lbl_titulo)
        
        txt_priv = TextInput(text=new_priv, readonly=True, size_hint_y=None, height=dp(70), font_size='11sp', halign='center')
        content.add_widget(txt_priv)
        
        btn_copiar = Button(text="COPIAR CLAVE", size_hint_y=None, height=dp(45), background_color=(0.1, 0.8, 0.3, 1))
        content.add_widget(btn_copiar)
        
        btn = Button(text="LA HE GUARDADO", size_hint_y=None, height=dp(50), background_color=(0,1,0.4,1))
        content.add_widget(btn)
        
        pop = Popup(title="Nueva Wallet", content=content, size_hint=(0.9, None), height=dp(380), auto_dismiss=False)
        
        def copiar_clave(instance):
            Clipboard.copy(new_priv)
            notif = Popup(title="Copiado", content=Label(text="Clave copiada"), size_hint=(0.6, None), height=dp(150))
            notif.open()
            Clock.schedule_once(lambda dt: notif.dismiss(), 1.5)
        
        btn_copiar.bind(on_release=copiar_clave)
        
        def save(instance):
            JsonStore('vlc_secure.json').put('user', address=addr, pub=pub, priv=priv_norm)
            pop.dismiss()
            self.manager.current = 'main'
        btn.bind(on_release=save)
        pop.open()

    def show_import_dialog(self):
        box = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        inp = TextInput(hint_text="Clave Privada Hex (64 caracteres)", password=True, multiline=False, size_hint_y=None, height=dp(50))
        btn = Button(text="IMPORTAR", background_color=(0.1, 0.45, 1, 1), size_hint_y=None, height=dp(50))
        box.add_widget(inp)
        box.add_widget(btn)
        pop = Popup(title="Importar", content=box, size_hint=(0.9, None), height=dp(250))

        def do_import(instance):
            priv = inp.text.strip().lower().replace(' ', '')
            if len(priv) != 64 or not all(c in '0123456789abcdef' for c in priv):
                self.mostrar_notificacion("Error", "La clave privada debe ser 64 caracteres hexadecimales")
                return
            
            addr, pub, priv_norm = derivar_wallet_oficial(priv)
            if addr:
                JsonStore('vlc_secure.json').put('user', address=addr, pub=pub, priv=priv_norm)
                pop.dismiss()
                self.manager.current = 'main'
            else:
                self.mostrar_notificacion("Error", "Clave privada inválida")
        btn.bind(on_release=do_import)
        pop.open()
    
    def mostrar_notificacion(self, titulo, mensaje):
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        label = Label(text=mensaje, font_size='14sp', halign='center', valign='middle', size_hint_y=None, text_size=(self.width * 0.65, None), markup=True)
        label.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll.add_widget(label)
        layout.add_widget(scroll)
        btn_ok = Button(text="OK", size_hint_y=None, height=dp(45), background_color=(0.1, 0.45, 1, 1))
        layout.add_widget(btn_ok)
        pop = Popup(title=titulo, content=layout, size_hint=(0.85, None), height=dp(280), auto_dismiss=False)
        btn_ok.bind(on_release=pop.dismiss)
        pop.open()


class VelCoinApp(App):
    def build(self):
        Builder.load_string(KV)
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(MainScreen(name='main'))
        if JsonStore('vlc_secure.json').exists('user'):
            sm.current = 'main'
        return sm

if __name__ == '__main__':
    VelCoinApp().run()
