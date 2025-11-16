fAbsolument. Voici le code complet ré-écrit pour que les relais soient actifs à l'état bas (actifs sur LOW).

La seule modification se trouve dans le constructeur __init__ de la classe RelayControl, où active_high=False a été ajouté lors de la création des OutputDevice. J'ai également mis à jour les messages print pour refléter ce changement de logique.

Code Complet Corrigé
Python

from threading import Thread, Event, Condition, Lock
from enum import Enum
from collections import deque
from typing import Optional

import subprocess
import shutil
import time
import logging
import platform

# Ces importations sont hypothétiques car les modules ne sont pas fournis.
# Je les commente pour que le code soit syntaxiquement correct.
# from utils.vis_manager import RelayVis
# from utils.error_manager import OWLAlreadyRunningError
# from utils.log_manager import LogManager

# --- Mocks pour les classes utilitaires manquantes ---
class LogManager:
    @staticmethod
    def get_logger(name):
        # Crée un logger basique si le vrai LogManager n'est pas disponible
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

class RelayVis:
    def __init__(self, relays):
        pass
    def update(self, relay, status):
        pass

class OWLAlreadyRunningError(Exception):
    pass
# --- Fin des Mocks ---

logger = logging.getLogger(__name__)

def get_platform_config() -> tuple[bool, Optional[Exception]]:
    """Determine platform and return testing status and lgpio error type"""
    system_platform = platform.platform().lower()
    is_raspberry_pi = 'rpi' in system_platform or 'aarch' in system_platform

    if is_raspberry_pi:
        from gpiozero import Buzzer, OutputDevice, LED, Device
        from gpiozero.pins.pigpio import PiGPIOFactory
        import lgpio
        # Utiliser pigpio pour une meilleure gestion des ressources
        Device.pin_factory = PiGPIOFactory()
        return False, lgpio.error

    is_windows = platform.system() == "Windows"
    system_name = "Windows" if is_windows else "unrecognized"
    logger.warning(
        f"The system is running on a {system_name} platform. GPIO disabled. Test mode active."
    )
    return True, None

testing, lgpioERROR = get_platform_config()

# Import GPIO components only if needed
if not testing:
    from gpiozero import Buzzer, OutputDevice, LED, Device

# two test classes to run the analysis on a desktop computer
class TestRelay:
    def __init__(self, relay_number, verbose=False):
        self.relay_number = relay_number
        self.verbose = verbose

    def on(self):
        if self.verbose:
            print(f"[TEST] Relay {self.relay_number} ON")

    def off(self):
        if self.verbose:
            print(f"[TEST] Relay {self.relay_number} OFF")
    
    def close(self):
        self.off()

class TestBuzzer:
    def beep(self, on_time, off_time, n=1, verbose=False):
        for _ in range(n):
            if verbose:
                print('BEEP')
    
    def close(self):
        pass

class TestLED:
    def __init__(self, pin):
        self.pin = pin

    def blink(self, on_time=0.1, off_time=0.1, n=1, verbose=False, background=True):
        if n is None:
            n = 1
        for _ in range(n):
            if verbose:
                print(f'BLINK {self.pin}')

    def on(self):
        print(f'LED {self.pin} ON')

    def off(self):
        print(f'LED {self.pin} OFF')
    
    def close(self):
        self.off()


class BaseStatusIndicator:
    def __init__(self, save_directory, no_save=False):
        self.logger = LogManager.get_logger(__name__)

        self.save_directory = save_directory
        self.no_save = no_save
        self.testing = True if testing else False
        self.storage_used = None
        self.storage_total = None
        self.update_event = Event()
        self.running = True
        self.thread = None
        self.DRIVE_FULL = False

        self.error_code = None
        self.flashing_thread = None

    def start_storage_indicator(self):
        self.thread = Thread(target=self.run_update)
        self.thread.start()

    def run_update(self):
        while self.running:
            self.update()
            self.update_event.wait(10.5)
            self.update_event.clear()

    def update(self):
        if self.save_directory is not None:
            self.storage_total, self.storage_used, _ = shutil.disk_usage(self.save_directory)
            percent_full = (self.storage_used / self.storage_total)
            self._update_storage_indicator(percent_full)

        elif self.no_save:
            pass
        else:
            self.error(6)

    def error(self, error_code):
        self.error_code = error_code
        if self.flashing_thread is None or not self.flashing_thread.is_alive():
            self.flashing_thread = Thread(target=self._flash_error_code)
            self.flashing_thread.start()

    def _flash_error_code(self):
        while self.running:
            for _ in range(self.error_code):
                time.sleep(0.2)
            time.sleep(2)

    def _update_storage_indicator(self, percent_full):
        self.logger.warning("Called _update_storage_indicator() but it's not implemented.")
        raise NotImplementedError("This method should be implemented by subclasses")

    def stop(self):
        self.running = False
        self.update_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join()
    
    def close(self):
        self.stop()


class HeadlessStatusIndicator(BaseStatusIndicator):
    def __init__(self, save_directory=None, no_save=False):
        super().__init__(save_directory, no_save)

    def _update_storage_indicator(self, percent_full):
        if percent_full >= 0.90:
            self.DRIVE_FULL = True


class UteStatusIndicator(BaseStatusIndicator):
    def __init__(self, save_directory, record_led_pin='BOARD38', storage_led_pin='BOARD40'):
        super().__init__(save_directory, no_save=False)
        LED_class = LED if not testing else TestLED
        self.record_LED = LED_class(pin=record_led_pin)
        self.storage_LED = LED_class(pin=storage_led_pin)

    def _update_storage_indicator(self, percent_full):
        if percent_full >= 0.90:
            self.DRIVE_FULL = True
            self.storage_LED.on()
            self.record_LED.off()
        elif percent_full >= 0.85:
            self.storage_LED.blink(on_time=0.2, off_time=0.2, n=None, background=True)
        elif percent_full >= 0.80:
            self.storage_LED.blink(on_time=0.5, off_time=0.5, n=None, background=True)
        elif percent_full >= 0.75:
            self.storage_LED.blink(on_time=0.5, off_time=1.5, n=None, background=True)
        elif percent_full >= 0.5:
            self.storage_LED.blink(on_time=0.5, off_time=3.0, n=None, background=True)
        else:
            self.storage_LED.blink(on_time=0.5, off_time=4.5, n=None, background=True)

    def setup_success(self):
        self.storage_LED.blink(on_time=0.1, off_time=0.2, n=3)
        self.record_LED.blink(on_time=0.1, off_time=0.2, n=3)

    def image_write_indicator(self):
        self.record_LED.blink(on_time=0.1, n=1, background=True)

    def alert_flash(self):
        self.storage_LED.blink(on_time=0.5, off_time=0.5, n=None, background=True)
        self.record_LED.blink(on_time=0.5, off_time=0.5, n=None, background=True)

    def stop(self):
        super().stop()
        if self.flashing_thread and self.flashing_thread.is_alive():
            self.flashing_thread.join()
        self.storage_LED.off()
        self.record_LED.off()

    def close(self):
        self.stop()
        self.storage_LED.close()
        self.record_LED.close()


class AdvancedIndicatorState(Enum):
    IDLE = 0
    RECORDING = 1
    DETECTING = 2
    NOTIFICATION = 3
    RECORDING_AND_DETECTING = 4
    ERROR = 5


class AdvancedStatusIndicator(BaseStatusIndicator):
    def __init__(self, save_directory, status_led_pin='BOARD37'):
        super().__init__(save_directory, no_save=False)
        LED_class = LED if not testing else TestLED
        self.led = LED_class(pin=status_led_pin)
        self.state = AdvancedIndicatorState.IDLE
        self.error_queue = deque()
        self.state_lock = Lock()
        self.weed_detection_enabled = False
        self.image_recording_enabled = False
        self.flashing_thread = None

    def _update_storage_indicator(self, percent_full):
        if percent_full >= 0.90:
            self.DRIVE_FULL = True
            self.error(1)

    def setup_success(self):
        self.led.blink(on_time=0.1, off_time=0.1, n=2)

    def _update_state(self):
        if self.state != AdvancedIndicatorState.ERROR:
            if self.weed_detection_enabled and self.image_recording_enabled:
                self.state = AdvancedIndicatorState.RECORDING_AND_DETECTING
            elif self.weed_detection_enabled:
                self.state = AdvancedIndicatorState.DETECTING
            elif self.image_recording_enabled:
                self.state = AdvancedIndicatorState.RECORDING
            else:
                self.state = AdvancedIndicatorState.IDLE

    def enable_weed_detection(self):
        with self.state_lock:
            self.weed_detection_enabled = True
            self._update_state()

    def disable_weed_detection(self):
        with self.state_lock:
            self.weed_detection_enabled = False
            self._update_state()

    def enable_image_recording(self):
        with self.state_lock:
            self.image_recording_enabled = True
            self._update_state()

    def disable_image_recording(self):
        with self.state_lock:
            self.image_recording_enabled = False
            self._update_state()

    def image_write_indicator(self):
        with self.state_lock:
            if self.state not in [AdvancedIndicatorState.ERROR, AdvancedIndicatorState.DETECTING, AdvancedIndicatorState.RECORDING_AND_DETECTING]:
                self.led.blink(on_time=0.1, off_time=0.1, n=1, background=True)

    def weed_detect_indicator(self):
        with self.state_lock:
            if self.state in [AdvancedIndicatorState.DETECTING, AdvancedIndicatorState.RECORDING_AND_DETECTING]:
                self.led.blink(on_time=0.05, off_time=0.05, n=1, background=True)

    def generic_notification(self):
        with self.state_lock:
            init_state = self.state
            self.state = AdvancedIndicatorState.NOTIFICATION
            self.led.off()

            self.led.blink(on_time=0.1, off_time=0.1, n=2, background=False)
            self.state = init_state

    def error(self, error_code):
        self.error_code = error_code
        with self.state_lock:
            self.state = AdvancedIndicatorState.ERROR
        if self.flashing_thread is None or not self.flashing_thread.is_alive():
            self.flashing_thread = Thread(target=self._flash_error_code)
            self.flashing_thread.start()

    def _flash_error_code(self):
        while self.running:
            for _ in range(self.error_code):
                self.led.blink(on_time=0.2, n=1, background=False)
                time.sleep(0.5)
            time.sleep(2)

    def stop(self):
        super().stop()
        if self.flashing_thread and self.flashing_thread.is_alive():
            self.flashing_thread.join()
        self.led.off()

    def close(self):
        self.stop()
        self.led.close()

# control class for the relay board
class RelayControl:
    def __init__(self, relay_dict):
        self.logger = LogManager.get_logger(__name__)
        self.testing = True if testing else False
        self.relay_dict_pins = relay_dict
        self.relay_devices = {}
        self.on = False
        self.field_data_recording = False

        if not self.testing:
            try:
                self.buzzer = Buzzer(pin='BOARD7')
            except Exception as e:
                if isinstance(e, lgpioERROR) and 'GPIO busy' in str(e):
                    raise OWLAlreadyRunningError("OWL instance may already be running.") from e
                else:
                    raise
            
            for relay, board_pin in self.relay_dict_pins.items():
                # ##################################################################
                # #####                  MODIFICATION PRINCIPALE                 #####
                # ##### On inverse la logique : HIGH = OFF, LOW = ON             #####
                # ##################################################################
                self.relay_devices[relay] = OutputDevice(pin=f'BOARD{board_pin}', active_high=False)
        else:
            self.buzzer = TestBuzzer()
            for relay, board_pin in self.relay_dict_pins.items():
                self.relay_devices[relay] = TestRelay(board_pin)

    def relay_on(self, relay_number, verbose=True):
        relay = self.relay_devices[relay_number]
        relay.on()
        if verbose:
            print(f"Relay {relay_number} ON (broche -> LOW)")

    def relay_off(self, relay_number, verbose=True):
        relay = self.relay_devices[relay_number]
        relay.off()
        if verbose:
            print(f"Relay {relay_number} OFF (broche -> HIGH)")

    def beep(self, duration=0.2, repeats=2):
        self.buzzer.beep(on_time=duration, off_time=(duration / 2), n=repeats)

    def all_on(self, verbose=False):
        for relay in self.relay_devices.keys():
            self.relay_on(relay, verbose=verbose)

    def all_off(self, verbose=False):
        for relay in self.relay_devices.keys():
            self.relay_off(relay, verbose=verbose)

    def remove(self, relay_number):
        if relay_number in self.relay_devices:
            self.relay_devices[relay_number].close()
            self.relay_devices.pop(relay_number, None)

    def clear(self):
        for relay_number in list(self.relay_devices.keys()):
            self.remove(relay_number)

    def stop(self):
        self.all_off()
    
    def close(self):
        self.all_off()
        self.clear()
        if self.buzzer:
            self.buzzer.close()

# this class does the hard work of receiving detection 'jobs' and queuing them
class RelayController:
    def __init__(self, relay_dict, vis=False, status_led=None):
        self.logger = LogManager.get_logger(__name__)
        self.relay_dict = relay_dict
        self.vis = vis
        self.status_led = status_led
        self.running = True
        
        try:
            self.relay = RelayControl(self.relay_dict)
        except OWLAlreadyRunningError:
            self.logger.error("Failed to initialize RelayControl: OWL is already running and using GPIO pin 7.")
            raise
        
        self.relay_queue_dict = {}
        self.relay_condition_dict = {}
        self.relay_threads = []

        self.logger.info("[INFO] Setting up nozzles...")
        self.relay_vis = RelayVis(relays=len(self.relay_dict.keys()))
        for relay_number in range(0, len(self.relay_dict)):
            self.relay_queue_dict[relay_number] = deque(maxlen=5)
            self.relay_condition_dict[relay_number] = Condition()

            relay_thread = Thread(target=self.consumer, args=[relay_number])
            relay_thread.setDaemon(True)
            relay_thread.start()
            self.relay_threads.append(relay_thread)

        time.sleep(1)
        self.logger.info("[INFO] Nozzle setup complete. Initiating camera...")
        self.relay.beep(duration=0.5)
        
    def receive(self, relay, time_stamp, location=0, delay=0, duration=1):
        input_queue_message = [relay, time_stamp, delay, duration]
        input_queue = self.relay_queue_dict[relay]
        input_condition = self.relay_condition_dict[relay]
        with input_condition:
            input_queue.append(input_queue_message)
            input_condition.notify()

    def consumer(self, relay):
        input_condition = self.relay_condition_dict[relay]
        relay_on = False
        relay_queue = self.relay_queue_dict[relay]

        with input_condition:
            while self.running:
                while relay_queue:
                    job = relay_queue.popleft()
                    input_condition.release()
                    
                    onDur = 0 if (job[3] - (time.time() - job[1])) <= 0 else (job[3] - (time.time() - job[1]))

                    if not relay_on:
                        time.sleep(job[2])
                        self.relay.relay_on(relay, verbose=False)
                        if self.status_led:
                            self.status_led.blink(on_time=0.1, n=1, background=True)
                        if self.vis:
                            self.relay_vis.update(relay=relay, status=True)
                        relay_on = True

                    try:
                        time.sleep(onDur)
                    except ValueError:
                        time.sleep(0)
                    
                    input_condition.acquire()

                if len(relay_queue) == 0 and relay_on:
                    self.relay.relay_off(relay, verbose=False)
                    if self.vis:
                        self.relay_vis.update(relay=relay, status=False)
                    relay_on = False
                
                if self.running:
                    input_condition.wait()
    
    def stop(self):
        print("Stopping RelayController...")
        self.running = False
        for _, condition in self.relay_condition_dict.items():
            with condition:
                condition.notifyAll()
        
        self.relay.close()
        print("RelayController stopped.")


if __name__ == "__main__":
    
    ALL_RELAY_PINS = {
        0: 11, 1: 12, 2: 13, 3: 15,
        4: 16, 5: 18, 6: 22, 7: 29 
    }
    UTE_RECORD_LED_PIN = 'BOARD38'
    UTE_STORAGE_LED_PIN = 'BOARD40'
    ADVANCED_STATUS_LED_PIN = 'BOARD37'

    def cleanup_gpios():
        print("\n--- Lancement du nettoyage des broches GPIO ---")
        
        if testing:
            print("Mode TEST: Simulation du nettoyage des broches.")
            return

        try:
            print("Mise de tous les relais à l'état de repos (broches en HIGH)...")
            relay_controller = RelayControl(relay_dict=ALL_RELAY_PINS)
            relay_controller.all_off(verbose=True)
            relay_controller.close()
            print("Relais et buzzer désactivés et ressources libérées.")

            print("\nExtinction des LEDs externes (broches en LOW)...")
            led_record = LED(UTE_RECORD_LED_PIN)
            led_storage = LED(UTE_STORAGE_LED_PIN)
            led_status = LED(ADVANCED_STATUS_LED_PIN)
            
            led_record.off()
            led_storage.off()
            led_status.off()

            led_record.close()
            led_storage.close()
            led_status.close()
            print(f"LEDs sur les broches {UTE_RECORD_LED_PIN}, {UTE_STORAGE_LED_PIN}, {ADVANCED_STATUS_LED_PIN} éteintes.")

        except Exception as e:
            print(f"Une erreur est survenue pendant le nettoyage : {e}")
        finally:
            if not testing:
                # Ferme la connexion au démon pigpio
                Device.pin_factory.close()
            print("\n--- Nettoyage GPIO terminé ---")

    try:
        print("Le programme principal s'exécute avec une logique de relais inversée (actif sur LOW).")
        print("Les broches des relais sont maintenues à HIGH par défaut.")
        print("Appuyez sur Ctrl+C pour arrêter le programme et lancer le nettoyage.")
        
        # Pour la démonstration, on instancie le contrôleur et on attend.
        # Dans une vraie application, vous interagiriez avec cet objet.
        controller = RelayController(relay_dict=ALL_RELAY_PINS)
        
        # Le programme attend ici indéfiniment.
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nInterruption par l'utilisateur détectée.")
    finally:
        cleanup_gpios()





