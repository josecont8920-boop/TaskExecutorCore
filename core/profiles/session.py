from .profile import Profile

class Session:
    def __init__(self, profile: Profile, driver):
        self.profile = profile
        self.driver = driver

    def navigate(self, url: str):
        print(f"Navegando a {url} usando perfil {self.profile.name} con UA: {self.profile.user_agent}")

    def close(self):
        print(f"Cerrando sesión del perfil {self.profile.name}")
