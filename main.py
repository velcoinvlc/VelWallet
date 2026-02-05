#!/usr/bin/env python3
import os
import json
import requests
import time
import hashlib
import qrcode
from io import BytesIO
from ecdsa import SigningKey, SECP256k1
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.core.image import Image as CoreImage
from kivy.storage.jsonstore import JsonStore
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard

NODE_URL = "https://velcoin.onrender.com"

try:
    Builder.load_file("wallet.kv")
    print("✅ wallet.kv cargado")
except:
    print("⚠️ wallet.kv no encontrado")

class WalletManager:
    @staticmethod
    def create_wallet():
        sk = SigningKey.generate(curve=SECP256k1)
        vk = sk.get_verifying_key()
        wallet = {
            "private_key": sk.to_string().hex(),
            "public_key": vk.to_string().hex(),
            "address": hashlib.sha256(vk.to_string()).hexdigest()[:40]
        }
        WalletManager.save_wallet(wallet)
        return wallet
    
    @staticmethod
    def import_wallet(private_key, address):
        try:
            sk = SigningKey.from_string(bytes.fromhex(private_key), curve=SECP256k1)
            vk = sk.get_verifying_key()
            wallet = {
                "private_key": private_key,
                "public_key": vk.to_string().hex(),
                "address": address
            }
            WalletManager.save_wallet(wallet)
            return wallet
        except:
            return None
    
    @staticmethod
    def save_wallet(wallet):
        store = JsonStore("wallet.json")
        store.put('wallet', data=wallet)
    
    @staticmethod
    def load_wallet():
        store = JsonStore("wallet.json")
        if store.exists('wallet'):
            return store.get('wallet')['data']
        return None
    
    @staticmethod
    def clear_wallet():
        store = JsonStore("wallet.json")
        if store.exists('wallet'):
            store.delete('wallet')
    
    @staticmethod
    def save_history(tx):
        store = JsonStore("wallet_history.json")
        history = WalletManager.load_history()
        history.append(tx)
        store.put('history', data=history)
    
    @staticmethod
    def load_history():
        store = JsonStore("wallet_history.json")
        if store.exists('history'):
            return store.get('history')['data']
        return []
    
    @staticmethod
    def get_balance(address, callback):
        try:
            response = requests.get(f"{NODE_URL}/balance/{address}", timeout=10)
            data = response.json()
            callback(data if response.status_code == 200 else None)
        except:
            callback(None)
    
    @staticmethod
    def send_transaction(wallet, recipient, amount, callback):
        try:
            sender = wallet["address"]
            sk = SigningKey.from_string(bytes.fromhex(wallet["private_key"]), curve=SECP256k1)
            msg = f"{sender}->{recipient}:{amount}"
            msg_hash = hashlib.sha256(msg.encode()).hexdigest()
            signature = sk.sign(bytes.fromhex(msg_hash)).hex()
            
            payload = {
                "from": sender,
                "to": recipient,
                "amount": amount,
                "signature": signature,
                "public_key": wallet["public_key"]
            }
            
            response = requests.post(f"{NODE_URL}/transfer", json=payload, timeout=10)
            result = response.json() if response.status_code == 200 else None
            
            if result and result.get("status") == "success":
                WalletManager.save_history({
                    "tx_hash": result["tx_hash"],
                    "from": sender,
                    "to": recipient,
                    "amount": amount,
                    "timestamp": time.time()
                })
            
            callback(result)
        except Exception as e:
            callback({"error": str(e)})

class MessagePopup(Popup):
    def __init__(self, title, message, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.size_hint = (0.85, 0.4)
        self.auto_dismiss = True
        
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        label = Label(text=message, halign='center', valign='middle', font_size=sp(14))
        label.bind(size=label.setter('text_size'))
        layout.add_widget(label)
        
        btn = Button(text='OK', size_hint_y=None, height=dp(40), font_size=sp(16))
        btn.bind(on_press=self.dismiss)
        layout.add_widget(btn)
        
        self.content = layout

class CreateWalletPopup(Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Wallet Creada - ¡GUARDA ESTO!"
        self.size_hint = (0.95, 0.85)
        self.auto_dismiss = False
        
        self.wallet = WalletManager.create_wallet()
        
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(12))
        
        # Dirección
        layout.add_widget(Label(text="DIRECCIÓN:", font_size=sp(18), bold=True, size_hint_y=None, height=dp(35)))
        self.addr_label = Label(text=self.wallet['address'], font_size=sp(14), size_hint_y=None, height=dp(60))
        self.addr_label.bind(size=self.addr_label.setter('text_size'))
        layout.add_widget(self.addr_label)
        
        # Clave Privada
        layout.add_widget(Label(text="CLAVE PRIVADA:", font_size=sp(18), bold=True, size_hint_y=None, height=dp(35)))
        
        priv_display = f"{self.wallet['private_key'][:14]}...{self.wallet['private_key'][-14:]}"
        self.priv_label = Label(text=priv_display, font_size=sp(14), size_hint_y=None, height=dp(60))
        self.priv_label.bind(size=self.priv_label.setter('text_size'))
        self.priv_label.full_key = self.wallet['private_key']
        layout.add_widget(self.priv_label)
        
        # Copiar Clave Privada
        btn_copy = Button(text="📋 Copiar Clave Privada", size_hint_y=None, height=dp(50), font_size=sp(16), background_color=(0.2, 0.5, 0.9, 1))
        btn_copy.bind(on_press=self.copy_private_key)
        layout.add_widget(btn_copy)
        
        # Mostrar Clave Completa
        btn_show = Button(text="👁️ Mostrar Clave Completa", size_hint_y=None, height=dp(45), font_size=sp(15), background_color=(0.5, 0.5, 0.5, 1))
        btn_show.bind(on_press=self.show_full_key)
        layout.add_widget(btn_show)
        
        # Continuar
        self.btn_continue = Button(text="Continuar a la Wallet ➡️", size_hint_y=None, height=dp(50), font_size=sp(16), background_color=(0, 1, 0.5, 0.5), disabled=True)
        self.btn_continue.bind(on_press=self.continue_to_wallet)
        layout.add_widget(self.btn_continue)
        
        self.copied = False
        self.content = layout
    
    def copy_private_key(self, instance):
        """Copia con portapapeles nativo"""
        try:
            Clipboard.copy(self.wallet['private_key'])
            self.copied = True
            instance.text = "✅ Copiada!"
            instance.background_color = (0, 1, 0.5, 1)
            
            self.btn_continue.disabled = False
            self.btn_continue.background_color = (0, 1, 0.5, 1)
            
            MessagePopup(
                "⚠️ GUARDA TU CLAVE PRIVADA",
                "¡ESTA ES LA ÚNICA VEZ QUE SE MOSTRARÁ!\n\nSi la pierdes, perderás ACCESO PERMANENTE a tus fondos."
            ).open()
        except:
            self._save_to_file_fallback()
    
    def _save_to_file_fallback(self):
        try:
            path = f"/sdcard/Download/CLAVE_PRIVADA_{self.wallet['address'][:8]}.txt"
            with open(path, "w") as f:
                f.write(f"DIRECCIÓN: {self.wallet['address']}\nPRIVATE KEY: {self.wallet['private_key']}\n")
            MessagePopup("✅ Guardado", f"Clave en: {path}").open()
            self.copied = True
            self.btn_continue.disabled = False
            self.btn_continue.background_color = (0, 1, 0.5, 1)
        except:
            MessagePopup("Error", "No se pudo copiar ni guardar").open()
    
    def show_full_key(self, instance):
        self.priv_label.text = self.wallet['private_key']
        self.priv_label.font_size = sp(9)
        instance.text = "✓ Clave visible"
        instance.disabled = True
    
    def continue_to_wallet(self, instance):
        if not self.copied:
            MessagePopup("Advertencia", "Copia la clave antes de continuar").open()
            return
        
        self.dismiss()
        App.get_running_app().root.current = 'main'
        App.get_running_app().root.get_screen('main').load_dashboard()

class ImportWalletPopup(Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Importar Wallet"
        self.size_hint = (0.95, 0.6)
        self.auto_dismiss = False
        
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        layout.add_widget(Label(text="Clave Privada:", font_size=sp(16), size_hint_y=None, height=dp(30)))
        self.priv_input = TextInput(
            hint_text="Pega tu clave privada",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(50),
            font_size=sp(14)
        )
        layout.add_widget(self.priv_input)
        
        layout.add_widget(Label(text="Dirección:", font_size=sp(16), size_hint_y=None, height=dp(30)))
        self.addr_input = TextInput(
            hint_text="Pega tu dirección",
            multiline=False,
            size_hint_y=None,
            height=dp(50),
            font_size=sp(14)
        )
        layout.add_widget(self.addr_input)
        
        self.spinner_label = Label(
            text="Importando...",
            font_size=sp(16),
            color=(0, 1, 0.5, 1),
            opacity=0,
            size_hint_y=None,
            height=dp(30)
        )
        layout.add_widget(self.spinner_label)
        
        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.btn_import = Button(text="Importar", font_size=sp(16))
        self.btn_import.bind(on_press=lambda x: self.import_wallet())
        btn_cancel = Button(text="Cancelar", font_size=sp(16))
        btn_cancel.bind(on_press=self.dismiss)
        btn_box.add_widget(self.btn_import)
        btn_box.add_widget(btn_cancel)
        layout.add_widget(btn_box)
        
        self.content = layout
    
    def import_wallet(self):
        self.spinner_label.opacity = 1
        self.btn_import.disabled = True
        self.btn_import.text = "Importando..."
        
        Clock.schedule_once(self._do_import, 1.5)
    
    def _do_import(self, dt):
        priv = self.priv_input.text.strip()
        addr = self.addr_input.text.strip()
        
        if not priv or not addr:
            MessagePopup("Error", "Completa ambos campos").open()
            self._reset_ui()
            return
        
        wallet = WalletManager.import_wallet(priv, addr)
        if wallet:
            self.priv_input.text = ""
            self.addr_input.text = ""
            self.dismiss()
            App.get_running_app().root.current = 'main'
            App.get_running_app().root.get_screen('main').load_dashboard()
        else:
            MessagePopup("Error", "Clave privada inválida").open()
        
        self._reset_ui()
    
    def _reset_ui(self):
        self.spinner_label.opacity = 0
        self.btn_import.disabled = False
        self.btn_import.text = "Importar"

class LoginScreen(Screen):
    def create_wallet_popup(self):
        popup = CreateWalletPopup()
        popup.open()
    
    def import_wallet_popup(self):
        popup = ImportWalletPopup()
        popup.open()

class MainScreen(Screen):
    def on_enter(self):
        self.load_dashboard()
    
    def load_dashboard(self):
        wallet = WalletManager.load_wallet()
        if not wallet:
            return
        
        self.ids.address_label.text = f"{wallet['address'][:8]}...{wallet['address'][-6:]}"
        
        def update_balance(data):
            if data and 'balance' in data:
                balance_value = float(data['balance'])
                balance_formatted = f"{balance_value:,.2f} VLC"
                
                self.ids.balance_label.text = balance_formatted
                # ✅ CONSULTAR PRECIO USD EN TIEMPO REAL
                self._fetch_usd_price(balance_value, data.get('usd_value', 0))
            else:
                self.ids.balance_label.text = "Error de conexión"
        
        WalletManager.get_balance(wallet['address'], update_balance)
    
    def _fetch_usd_price(self, balance, fallback_usd):
        """Consulta precio VelCoin desde CoinGecko"""
        try:
            coin_ids = ['velcoin', 'velcoin-2', 'vlc']
            price = 0
            
            for coin_id in coin_ids:
                response = requests.get(
                    f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd",
                    timeout=5
                )
                if response.status_code == 200:
                    price_data = response.json()
                    if coin_id in price_data and 'usd' in price_data[coin_id]:
                        price = price_data[coin_id]['usd']
                        break
            
            if price > 0:
                usd_value = balance * price
                self.ids.usd_label.text = f"≈ ${usd_value:,.2f}"
            elif fallback_usd > 0:
                self.ids.usd_label.text = f"≈ ${fallback_usd:,.2f}"
            else:
                self.ids.usd_label.text = "$0.00 (No listado)"
                
        except:
            if fallback_usd > 0:
                self.ids.usd_label.text = f"≈ ${fallback_usd:,.2f}"
            else:
                self.ids.usd_label.text = "$0.00 (Error API)"
    
    def logout(self):
        WalletManager.clear_wallet()
        self.manager.current = 'login'
    
    def show_receive(self):
        self.manager.current = 'receive'
    
    def show_send(self):
        self.manager.current = 'send'
    
    def show_history(self):
        self.manager.current = 'history'

class ReceiveScreen(Screen):
    def on_enter(self):
        wallet = WalletManager.load_wallet()
        if wallet:
            address = wallet['address']
            self.ids.addr_label.text = address
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(address)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#00FF88", back_color="#0A0E27")
            
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            self.ids.qr_image.texture = CoreImage(buf, ext='png').texture
    
    def save_address(self):
        address = self.ids.addr_label.text
        try:
            path = "/sdcard/Download/mi_direccion_velcoin.txt"
            with open(path, "w") as f:
                f.write(address)
            MessagePopup("Éxito", f"Dirección guardada en:\n{path}").open()
        except:
            MessagePopup("Error", "No se pudo guardar archivo").open()

class SendScreen(Screen):
    def scan_qr(self):
        """POPUP SIMPLE PARA QR (sin cámara)"""
        popup = Popup(title="Escáner QR", size_hint=(0.9, 0.4))
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        layout.add_widget(Label(text="Pega dirección escaneada", font_size=sp(14)))
        
        temp_input = TextInput(hint_text="Dirección", multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(temp_input)
        
        btn_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        btn_ok = Button(text="Usar")
        btn_ok.bind(on_press=lambda x: [setattr(self.ids.recipient_input, 'text', temp_input.text), popup.dismiss()])
        btn_cancel = Button(text="Cancelar")
        btn_cancel.bind(on_press=popup.dismiss)
        btn_box.add_widget(btn_ok)
        btn_box.add_widget(btn_cancel)
        layout.add_widget(btn_box)
        
        popup.content = layout
        popup.open()
    
    def send_vlc(self):
        recipient = self.ids.recipient_input.text.strip()
        amount_str = self.ids.amount_input.text.strip()
        
        if not recipient or not amount_str:
            MessagePopup("Error", "Completa todos los campos").open()
            return
        
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except:
            MessagePopup("Error", "Cantidad inválida").open()
            return
        
        wallet = WalletManager.load_wallet()
        
        def handle_result(result):
            if result and result.get("status") == "success":
                MessagePopup("Éxito", f"Transacción enviada!\nHash: {result['tx_hash'][:16]}...").open()
                self.ids.recipient_input.text = ""
                self.ids.amount_input.text = ""
                self.manager.current = 'main'
            else:
                error = result.get("error", "Error desconocido") if result else "No se pudo contactar el nodo"
                MessagePopup("Error", error).open()
        
        WalletManager.send_transaction(wallet, recipient, amount, handle_result)

class HistoryScreen(Screen):
    def on_enter(self):
        self.load_history()
    
    def load_history(self):
        history = WalletManager.load_history()
        layout = self.ids.history_layout
        
        layout.clear_widgets()
        
        if not history:
            layout.add_widget(Label(text="No hay transacciones", size_hint_y=None, height=dp(50)))
            return
        
        for tx in reversed(history):
            t = time.strftime('%Y-%m-%d %H:%M', time.localtime(tx["timestamp"]))
            
            item = BoxLayout(size_hint_y=None, height=dp(80), orientation='horizontal', padding=dp(10))
            
            info = BoxLayout(orientation='vertical')
            info.add_widget(Label(text=f"{tx['from'][:8]}... -> {tx['to'][:8]}...", font_size=sp(12)))
            info.add_widget(Label(text=f"{tx['amount']} VLC | Hash: {tx['tx_hash'][:12]}...", font_size=sp(10)))
            
            right = BoxLayout(orientation='vertical', size_hint_x=0.3)
            right.add_widget(Label(text=t, font_size=sp(10)))
            right.add_widget(Label(text=f"{tx['amount']} VLC", font_size=sp(12), bold=True))
            
            item.add_widget(info)
            item.add_widget(right)
            layout.add_widget(item)

class VelWalletApp(App):
    def build(self):
        try:
            with open("wallet.kv", "r", encoding="utf-8") as f:
                kv_content = f.read()
            Builder.load_string(kv_content)
        except:
            print("⚠️ Usando KV por defecto")
        
        sm = ScreenManager()
        sm.add_screen = sm.add_widget
        
        sm.add_screen(LoginScreen(name='login'))
        sm.add_screen(MainScreen(name='main'))
        sm.add_screen(ReceiveScreen(name='receive'))
        sm.add_screen(SendScreen(name='send'))
        sm.add_screen(HistoryScreen(name='history'))
        
        sm.current = 'login'
        
        return sm

if __name__ == '__main__':
    VelWalletApp().run()
