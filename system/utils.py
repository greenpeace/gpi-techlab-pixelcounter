import socket

# Utility function to resolve domain to IP


def resolve_ip_from_domain(domain):
    try:
        return socket.gethostbyname(domain)
    except socket.gaierror:
        return None
