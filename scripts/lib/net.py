"""Fait confiance au magasin de certificats de macOS plutot qu'au magasin
interne de Python.

Sur le Mac de Younes, un antivirus ou un VPN intercepte le TLS et injecte son
propre certificat racine. macOS lui fait confiance, le Python de python.org non,
d'ou des erreurs CERTIFICATE_VERIFY_FAILED en local. truststore branche Python
sur le trousseau systeme et la question disparait.

Aucun effet sur GitHub Actions, ou il n'y a pas d'interception : si truststore
n'est pas installe, on continue simplement sans.
"""

INJECTE = False

try:
    import truststore
    truststore.inject_into_ssl()
    INJECTE = True
except ImportError:
    pass
except Exception:
    pass


def diagnostic() -> str:
    if INJECTE:
        return "TLS : magasin de certificats du systeme (truststore)"
    return "TLS : magasin interne de Python"
