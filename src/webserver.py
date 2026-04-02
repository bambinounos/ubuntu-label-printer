"""Gestión del servidor web ht300_web.py como subproceso."""

import os
import signal
import subprocess
import threading


class WebServerManager:
    """Lanza y detiene ht300_web.py como proceso hijo."""

    def __init__(self):
        self.process = None
        self.port = 5080
        self._log_lines = []

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, port=5080, on_output=None):
        """Inicia el servidor web. Retorna (ok, message)."""
        if self.running:
            return True, f"Ya está corriendo en puerto {self.port} (PID {self.process.pid})"

        self.port = port
        script = self._find_script()
        if not script:
            return False, "No se encontró ht300_web.py"

        try:
            self.process = subprocess.Popen(
                ["python3", script, "--port", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid,
            )

            # Leer output en background
            if on_output:
                thread = threading.Thread(
                    target=self._read_output, args=(on_output,), daemon=True
                )
                thread.start()

            return True, f"Servidor web iniciado en http://localhost:{port} (PID {self.process.pid})"

        except Exception as e:
            self.process = None
            return False, f"Error al iniciar: {e}"

    def stop(self):
        """Detiene el servidor web. Retorna (ok, message)."""
        if not self.running:
            return True, "El servidor no estaba corriendo"

        try:
            pid = self.process.pid
            # Enviar SIGTERM al grupo de procesos
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
                self.process.wait(timeout=3)

            self.process = None
            return True, f"Servidor detenido (PID {pid})"

        except Exception as e:
            self.process = None
            return True, f"Servidor detenido ({e})"

    def get_url(self):
        return f"http://localhost:{self.port}"

    def _find_script(self):
        """Busca ht300_web.py en ubicaciones conocidas."""
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "ht300_web.py"),
            "/opt/label-printer/ht300_web.py",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _read_output(self, callback):
        """Lee stdout del proceso en background."""
        try:
            for line in self.process.stdout:
                line = line.strip()
                if line:
                    self._log_lines.append(line)
                    if len(self._log_lines) > 100:
                        self._log_lines.pop(0)
                    callback(line)
        except (ValueError, OSError):
            pass
