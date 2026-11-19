"""Ponto de entrada da demo (local: `python app.py`; Hugging Face Spaces: app_file)."""
try:
    import spaces  # type: ignore[import-not-found]  # só existe no Space (ZeroGPU)

    @spaces.GPU
    def _placeholder_gpu():
        """Nunca é chamada. O hardware ZeroGPU exige uma função @spaces.GPU."""
        return None
except ImportError:  # local ou fora do Space
    pass

from src.config import carregar_settings
from src.interface.config_demo import carregar_config_demo
from src.interface.montagem import montar_servico
from src.interface.ui import construir_demo, opcoes_launch

settings = carregar_settings()
config = carregar_config_demo()
if config.sal_padrao:
    print("AVISO: DEMO_SALT não definido; defina-o nos secrets para anonimizar visitantes com um sal próprio.")
demo = construir_demo(montar_servico(settings, config), config)

if __name__ == "__main__":
    demo.launch(**opcoes_launch())