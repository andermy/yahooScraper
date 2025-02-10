from scipy.stats import norm
import numpy as np

def black_scholes(S, K, T, r, sigma, option_type="call"):
    """
    Black-Scholes opsjonsprisformel.

    :param S: Underliggende aksjekurs
    :param K: Strike price
    :param T: Tid til utløp (i år)
    :param r: Risikofri rente
    :param sigma: Implisitt volatilitet
    :param option_type: "call" eller "put"
    :return: Opsjonspris
    """
    if T == 0:
        if option_type == "call":
            return max(0, S - K)
        elif option_type == "put":
            return max(0, K - S)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == "call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type == "put":
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

# Eksempel på bruk
#S = 400  # Underliggende aksjepris
#K = 410  # Strike-pris
#T = 30 / 365  # 30 dager til utløp
#r = 0.01  # Risikofri rente (1 %)
#sigma = 0.2  # Implisitt volatilitet (20 %)

#call_price = black_scholes(S, K, T, r, sigma, option_type="call")
#put_price = black_scholes(S, K, T, r, sigma, option_type="put")

#print(f"Call-opsjonspris: {call_price:.2f}")
#print(f"Put-opsjonspris: {put_price:.2f}")
