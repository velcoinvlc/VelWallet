import hashlib
import requests
import os
import threading
import secrets
import json
import time

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.lang import Builder
from kivy.storage.jsonstore import JsonStore
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.clipboard import Clipboard
from kivy.factory import Factory

# --- CONFIGURACIÓN DEL NODO ---
NODE_URL = "https://velcoin.onrender.com"

def sha256(msg):
    """Helper para SHA256"""
    if isinstance(msg, str):
        msg = msg.encode()
    return hashlib.sha256(msg).hexdigest()

def derivar_wallet_oficial(priv_hex):
    """
    Deriva wallet compatible con el nodo VelCoin.
    Según el nodo:
    - public_key = sha256(private_key)
    - address = sha256(public_key)[:40]
    """
    try:
        private_key = priv_hex.lower()
        public_key = sha256(private_key)
        address = sha256(public_key)[:40]
        return address, public_key, private_key
    except Exception as e:
        print(f"Error derivando wallet: {e}")
        return None, None, None

def firmar_transaccion_nodo(public_key, sender, destinatario, monto, nonce):
    """
    Firma compatible con el nodo VelCoin.
    """
    try:
        payload = f'{sender}{destinatario}{monto}{nonce}'
        pub_key_hash = sha256(public_key)
        signature = sha256(pub_key_hash + payload)
        return signature
    except Exception as e:
        print(f"Error en firma: {e}")
        return None

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
        Label:
            id: addr_hist
            text: "Dirección..."
            font_size: '10sp'
            color: (0.6, 0.6, 0.6, 1)
            halign: 'left'
            text_size: self.size

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

        Label:
            text: "VelCoin VLC"
            font_size: '22sp'
            bold: True
            size_hint_y: None
            height: dp(40)

        # Tarjeta de Balance
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: dp(160)
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
            Label:
                id: balance_main
                text: "Cargando..."
                font_size: '34sp'
                bold: True
            Label:
                id: wallet_addr_short
                text: "0x000...000"
                font_size: '10sp'
                color: (1, 1, 1, 0.5)

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
                Button:
                    text: "REFRESCAR"
                    size_hint_x: None
                    width: dp(80)
                    font_size: '10sp'
                    background_color: (0,0,0,0)
                    color: (0.1, 0.45, 1, 1)
                    on_release: root.actualizar_todo()

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
        
        # Logo en la parte superior
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

class MainScreen(Screen):
    # Referencias a popups activos para poder cerrarlos
    popup_envio = None
    popup_minando = None
    
    def on_enter(self):
        self.actualizar_todo()

    def actualizar_todo(self):
        store = JsonStore('vlc_secure.json')
        if store.exists('user'):
            addr = store.get('user')['address']
            self.ids.wallet_addr_short.text = f"{addr[:15]}..."
            threading.Thread(target=self.update_info, args=(addr,), daemon=True).start()

    def update_info(self, addr):
        try:
            # 1. Balance
            r_bal = requests.get(f"{NODE_URL}/balance/{addr}", timeout=10).json()
            balance = r_bal.get('balance', 0)

            # 2. Escaneo de /blocks para Historial con hash de transacción
            r_blocks = requests.get(f"{NODE_URL}/blocks", timeout=10).json()
            mis_txs = []
            for bloque in r_blocks:
                txs = bloque.get('transactions', [])
                block_hash = bloque.get('block_hash', '')
                for tx in txs:
                    if tx.get('from') == addr or tx.get('to') == addr:
                        # Crear hash único de transacción
                        tx_data = f"{tx.get('from')}{tx.get('to')}{tx.get('amount')}{tx.get('nonce')}"
                        tx_hash = sha256(tx_data)[:16]
                        mis_txs.append({
                            "remitente": tx.get('from'),
                            "destinatario": tx.get('to'),
                            "monto": tx.get('amount'),
                            "nonce": tx.get('nonce'),
                            "public_key": tx.get('public_key'),
                            "signature": tx.get('signature'),
                            "tx_hash": tx_hash,
                            "block_hash": block_hash,
                            "timestamp": bloque.get('timestamp', 0)
                        })
            mis_txs.reverse()
            Clock.schedule_once(lambda dt: self.refresh_ui(balance, mis_txs))
        except Exception as e:
            print(f"Error en update_info: {e}")
            Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", "No se pudo conectar al nodo"))

    def refresh_ui(self, bal, history):
        self.ids.balance_main.text = f"{bal:,.2f} VLC"
        self.ids.history_list.clear_widgets()
        store = JsonStore('vlc_secure.json')
        my_addr = store.get('user')['address']

        for tx in history:
            item = Factory.TransactionItem()
            es_envio = tx['remitente'] == my_addr
            item.ids.tipo_monto.text = f"{'-' if es_envio else '+'} {tx['monto']} VLC"
            item.ids.tipo_monto.color = (1, 0.4, 0.4, 1) if es_envio else (0.4, 1, 0.4, 1)
            item.ids.addr_hist.text = f"{'Para: ' if es_envio else 'De: '}{tx['destinatario' if es_envio else 'remitente'][:20]}..."
            
            # Guardar datos de transacción en el item para el popup
            item.tx_data = tx
            item.es_envio = es_envio
            
            # Hacer clickeable
            item.bind(on_touch_down=lambda inst, touch, t=tx, e=es_envio: self.mostrar_detalle_tx(t, e) if inst.collide_point(*touch.pos) else None)
            
            self.ids.history_list.add_widget(item)

    def mostrar_detalle_tx(self, tx, es_envio):
        """Muestra popup con detalles de la transacción"""
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        # Tipo de transacción
        tipo = "ENVIADO" if es_envio else "RECIBIDO"
        color = (1, 0.4, 0.4, 1) if es_envio else (0.4, 1, 0.4, 1)
        
        contenido = f"""
[b]Tipo:[/b] {tipo}
[b]Monto:[/b] {tx['monto']} VLC

[b]De:[/b]
{tx['remitente']}

[b]Para:[/b]
{tx['destinatario']}

[b]Hash TX:[/b]
{tx['tx_hash']}

[b]Block Hash:[/b]
{tx['block_hash'][:32]}...

[b]Nonce:[/b] {tx['nonce']}
[b]Timestamp:[/b] {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tx['timestamp']))}

[b]Firma:[/b]
{tx['signature'][:40]}...
        """.strip()
        
        scroll = ScrollView(size_hint=(1, 1))
        label = Label(
            text=contenido,
            markup=True,
            font_size='11sp',
            halign='left',
            valign='top',
            size_hint_y=None,
            text_size=(self.width * 0.75, None)
        )
        label.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
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
            title="Detalle de Transacción",
            content=layout,
            size_hint=(0.9, 0.7)
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
        
        self.popup_envio = Popup(title="Enviar VelCoin", content=layout, size_hint=(0.9, 0.4))

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
            
            # Generar nonce
            nonce = int(time.time() * 1000)
            
            firma = firmar_transaccion_nodo(
                store['pub'],
                store['address'],
                destino, 
                monto,
                nonce
            )
            
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
            
            def enviar_y_minar():
                try:
                    # Enviar transacción
                    r = requests.post(f"{NODE_URL}/send", json=payload, timeout=10)
                    respuesta = r.json()
                    
                    if respuesta.get('accepted'):
                        # Mostrar popup de minando
                        Clock.schedule_once(lambda dt: self.mostrar_popup_minando(), 0)
                        
                        # Minar automáticamente
                        try:
                            r_mine = requests.post(f"{NODE_URL}/mine", timeout=30)
                            resultado_mine = r_mine.json()
                            
                            if "index" in resultado_mine:
                                Clock.schedule_once(lambda dt: self.cerrar_minando_y_mostrar_exito("Transacción confirmada en bloque!"), 0)
                            else:
                                Clock.schedule_once(lambda dt: self.cerrar_minando_y_mostrar_exito("Transacción enviada (pendiente de confirmación)"), 0)
                        except Exception as e:
                            print(f"Error minando: {e}")
                            Clock.schedule_once(lambda dt: self.cerrar_minando_y_mostrar_exito("Transacción enviada (minado pendiente)"), 0)
                    else:
                        error = respuesta.get('error', 'Error desconocido')
                        Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Transacción rechazada: {error}"), 0)
                        
                except Exception as e:
                    print(f"Error: {e}")
                    Clock.schedule_once(lambda dt: self.mostrar_notificacion("Error", f"Fallo de conexión: {str(e)}"), 0)
                
                Clock.schedule_once(lambda dt: self.cerrar_popup_envio(), 0)
            
            threading.Thread(target=enviar_y_minar, daemon=True).start()

        btn.bind(on_release=confirmar)
        self.popup_envio.open()
    
    def mostrar_popup_minando(self):
        """Muestra el popup de minando y lo guarda para cerrarlo después"""
        content = BoxLayout(orientation='vertical', padding=dp(20))
        content.add_widget(Label(text="Transacción aceptada. Minando bloque..."))
        
        self.popup_minando = Popup(
            title="Minando",
            content=content,
            size_hint=(0.7, 0.3),
            auto_dismiss=False
        )
        self.popup_minando.open()
    
    def cerrar_popup_envio(self):
        """Cierra el popup de envío si está abierto"""
        if self.popup_envio:
            self.popup_envio.dismiss()
            self.popup_envio = None
    
    def cerrar_minando_y_mostrar_exito(self, mensaje):
        """Cierra el popup de minando y muestra el de éxito con botón OK"""
        # Cerrar popup de minando
        if self.popup_minando:
            self.popup_minando.dismiss()
            self.popup_minando = None
        
        # Mostrar popup de éxito con OK
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        layout.add_widget(Label(text=mensaje))
        
        btn_ok = Button(
            text="OK",
            size_hint_y=None,
            height=dp(45),
            background_color=(0.1, 0.45, 1, 1)
        )
        layout.add_widget(btn_ok)
        
        pop = Popup(
            title="Éxito",
            content=layout,
            size_hint=(0.7, 0.35),
            auto_dismiss=False
        )
        
        def cerrar_todo_y_refrescar(instance):
            pop.dismiss()
            self.actualizar_todo()
        
        btn_ok.bind(on_release=cerrar_todo_y_refrescar)
        pop.open()

    def mostrar_mi_direccion(self):
        addr = JsonStore('vlc_secure.json').get('user')['address']
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        layout.add_widget(TextInput(text=addr, readonly=True, size_hint_y=None, height=dp(50)))
        btn = Button(text="COPIAR AL PORTAPAPELES", background_color=(0.1, 0.8, 0.3, 1), size_hint_y=None, height=dp(50))
        layout.add_widget(btn)
        
        pop = Popup(title="Tu Dirección", content=layout, size_hint=(0.9, 0.4))
        btn.bind(on_release=lambda x: [Clipboard.copy(addr), pop.dismiss()])
        pop.open()

    def mostrar_notificacion(self, titulo, mensaje):
        pop = Popup(title=titulo, content=Label(text=mensaje), size_hint=(0.7, 0.3))
        pop.open()

    def logout(self):
        if os.path.exists('vlc_secure.json'): os.remove('vlc_secure.json')
        self.manager.current = 'login'

class LoginScreen(Screen):
    def create_new_wallet(self):
        new_priv = ''.join(secrets.choice('0123456789abcdef') for _ in range(64))
        addr, pub, priv_norm = derivar_wallet_oficial(new_priv)
        
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        content.add_widget(Label(text="GUARDA ESTA CLAVE (NO LA PIERDAS):", color=(1,0.8,0,1)))
        content.add_widget(TextInput(text=new_priv, readonly=True, size_hint_y=None, height=dp(70)))
        
        # Botón para copiar clave privada
        btn_copiar = Button(text="COPIAR CLAVE AL PORTAPAPELES", size_hint_y=None, height=dp(45), background_color=(0.1, 0.8, 0.3, 1))
        content.add_widget(btn_copiar)
        
        btn = Button(text="LA HE GUARDADO", size_hint_y=None, height=dp(50), background_color=(0,1,0.4,1))
        content.add_widget(btn)
        pop = Popup(title="Nueva Wallet", content=content, size_hint=(0.9, 0.55), auto_dismiss=False)
        
        # Función para copiar la clave
        def copiar_clave(instance):
            Clipboard.copy(new_priv)
            # Mostrar notificación temporal
            notif = Popup(title="Copiado", content=Label(text="Clave copiada al portapapeles"), size_hint=(0.6, 0.2))
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
        pop = Popup(title="Importar", content=box, size_hint=(0.9, 0.4))

        def do_import(instance):
            priv = inp.text.strip()
            priv = priv.lower().replace(' ', '')
            
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
        pop = Popup(title=titulo, content=Label(text=mensaje), size_hint=(0.7, 0.3))
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
