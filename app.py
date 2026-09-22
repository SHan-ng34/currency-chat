import re
import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///currency_chat.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------------
# Models
# -------------------------

class Message(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    msg_type   = db.Column(db.String(10), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class RateCache(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    base       = db.Column(db.String(10), nullable=False, default="USD")
    currency   = db.Column(db.String(10), nullable=False)
    rate       = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint("base", "currency", name="uq_base_currency"),)

# -------------------------
# Helpers
# -------------------------

CACHE_TTL_MINUTES = 30
API_BASE = "https://open.er-api.com/v6"

def now_utc():
    return datetime.now(timezone.utc)

def aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def get_rates(base="USD"):
    base = base.upper()
    sample = RateCache.query.filter_by(base=base).first()
    if sample and (now_utc() - aware(sample.updated_at)) < timedelta(minutes=CACHE_TTL_MINUTES):
        return {r.currency: r.rate for r in RateCache.query.filter_by(base=base).all()}
    try:
        data = requests.get(f"{API_BASE}/latest/{base}", timeout=5).json()
        if data.get("result") != "success":
            return {r.currency: r.rate for r in RateCache.query.filter_by(base=base).all()}
        live = data["rates"]
        for code, rate in live.items():
            row = RateCache.query.filter_by(base=base, currency=code).first()
            if row:
                row.rate = rate
                row.updated_at = now_utc()
            else:
                db.session.add(RateCache(base=base, currency=code, rate=rate))
        db.session.commit()
        return live
    except Exception:
        return {r.currency: r.rate for r in RateCache.query.filter_by(base=base).all()}

# -------------------------
# Number formatting
# -------------------------

# Currencies that use the Indian numbering system (XX,XX,XXX)
INDIAN_SYSTEM_CURRENCIES = {"INR", "PKR", "NPR", "LKR", "BDT", "MUR", "SCR"}

def format_number(value, currency=None):
    """Format number with correct numbering system based on currency."""
    is_indian = currency and currency.upper() in INDIAN_SYSTEM_CURRENCIES

    if is_indian:
        is_negative = value < 0
        value = abs(value)
        if value == int(value):
            s = str(int(value))
            decimal_part = None
        else:
            s = f"{value:.2f}"
            integer_part, decimal_part = s.split('.')
            s = integer_part

        integer_part = s
        if len(integer_part) <= 3:
            result = integer_part
        else:
            result = integer_part[-3:]
            integer_part = integer_part[:-3]
            while integer_part:
                result = integer_part[-2:] + ',' + result
                integer_part = integer_part[:-2]

        if decimal_part:
            result = result + '.' + decimal_part
        return ('-' if is_negative else '') + result
    else:
        if value == int(value):
            return f"{int(value):,}"
        return f"{value:,.2f}"

# -------------------------
# Symbol map
# -------------------------

SYMBOL_MAP = {
    "$":"USD","C$":"CAD","A$":"AUD","NZ$":"NZD","S$":"SGD",
    "HK$":"HKD","MX$":"MXN","AR$":"ARS","R$":"BRL","€":"EUR",
    "£":"GBP","¥":"JPY","₹":"INR","₽":"RUB","₺":"TRY",
    "₩":"KRW","₪":"ILS","R":"ZAR","CHF":"CHF","฿":"THB",
    "₫":"VND","₦":"NGN","₲":"PYG","₡":"CRC","₴":"UAH",
    "₸":"KZT","₼":"AZN","₾":"GEL","د.إ":"AED","﷼":"SAR","kr":"SEK"
}

# -------------------------
# Word map — comprehensive
# -------------------------

WORD_MAP = {
    # ---- Single words ----
    "dollar":"USD","dollars":"USD",
    "euro":"EUR","euros":"EUR",
    "pound":"GBP","pounds":"GBP",
    "yen":"JPY",
    "rupee":"INR","rupees":"INR",
    "won":"KRW",
    "lira":"TRY",
    "ruble":"RUB","rubles":"RUB",
    "franc":"CHF","francs":"CHF",
    "rand":"ZAR",
    "baht":"THB",
    "dong":"VND",
    "dirham":"AED","dirhams":"AED",
    "riyal":"SAR","riyals":"SAR",
    "rial":"OMR","rials":"OMR",
    "krona":"SEK","krone":"NOK",
    "peso":"MXN","pesos":"MXN",
    "real":"BRL","reais":"BRL",
    "yuan":"CNY","renminbi":"CNY",
    "ringgit":"MYR",
    "rupiah":"IDR",
    "hryvnia":"UAH",
    "tenge":"KZT",
    "shekel":"ILS","shekels":"ILS",
    "dinar":"KWD","dinars":"KWD",
    "koruna":"CZK",
    "forint":"HUF",
    "zloty":"PLN",
    "lev":"BGN",
    "lei":"RON",
    "dram":"AMD",
    "manat":"AZN",
    "lari":"GEL",
    "som":"KGS",
    "tugrik":"MNT",
    "kyat":"MMK",
    "kip":"LAK",
    "riel":"KHR",
    "taka":"BDT",
    "birr":"ETB",
    "shilling":"KES",
    "cedi":"GHS",
    "naira":"NGN",
    "colón":"CRC","colon":"CRC",
    "quetzal":"GTQ",
    "lempira":"HNL",
    "córdoba":"NIO","cordoba":"NIO",
    "balboa":"PAB",
    "guaraní":"PYG","guarani":"PYG",
    "boliviano":"BOB",
    "sol":"PEN",
    # ---- Lowercase ISO fallbacks ----
    "pkr":"PKR","inr":"INR","usd":"USD","eur":"EUR",
    "gbp":"GBP","jpy":"JPY","cad":"CAD","aud":"AUD",
    "aed":"AED","sgd":"SGD","thb":"THB","myr":"MYR",
    "chf":"CHF","cny":"CNY","hkd":"HKD","nzd":"NZD",
    "sek":"SEK","nok":"NOK","dkk":"DKK","krw":"KRW",
    "try":"TRY","rub":"RUB","brl":"BRL","zar":"ZAR",
    "mxn":"MXN","idr":"IDR","php":"PHP","twd":"TWD",
    "lkr":"LKR","npr":"NPR","bdt":"BDT","vnd":"VND",
    "ngn":"NGN","kes":"KES","egp":"EGP","sar":"SAR",
    # ---- Dollar variants ----
    "us dollar":"USD","us dollars":"USD",
    "american dollar":"USD","american dollars":"USD",
    "australian dollar":"AUD","australian dollars":"AUD",
    "canadian dollar":"CAD","canadian dollars":"CAD",
    "singaporean dollar":"SGD","singaporean dollars":"SGD",
    "singapore dollar":"SGD","singapore dollars":"SGD",
    "new zealand dollar":"NZD","new zealand dollars":"NZD",
    "hong kong dollar":"HKD","hong kong dollars":"HKD",
    "zimbabwean dollar":"ZWL","zimbabwe dollar":"ZWL",
    "bahamian dollar":"BSD","bahamas dollar":"BSD",
    "barbadian dollar":"BBD","barbados dollar":"BBD",
    "belize dollar":"BZD","belizean dollar":"BZD",
    "brunei dollar":"BND","bruneian dollar":"BND",
    "fijian dollar":"FJD","fiji dollar":"FJD",
    "guyanese dollar":"GYD","guyana dollar":"GYD",
    "jamaican dollar":"JMD","jamaica dollar":"JMD",
    "namibian dollar":"NAD","namibia dollar":"NAD",
    "taiwan dollar":"TWD","taiwanese dollar":"TWD",
    "trinidad dollar":"TTD","trinidadian dollar":"TTD",
    # ---- Rupee variants ----
    "indian rupee":"INR","indian rupees":"INR",
    "pakistani rupee":"PKR","pakistani rupees":"PKR",
    "pakistan rupee":"PKR","pakistan rupees":"PKR",
    "nepalese rupee":"NPR","nepalese rupees":"NPR",
    "nepal rupee":"NPR","nepal rupees":"NPR",
    "sri lankan rupee":"LKR","sri lankan rupees":"LKR",
    "sri lanka rupee":"LKR","sri lanka rupees":"LKR",
    "mauritian rupee":"MUR","mauritian rupees":"MUR",
    "mauritius rupee":"MUR","mauritius rupees":"MUR",
    "seychellois rupee":"SCR","seychellois rupees":"SCR",
    "seychelles rupee":"SCR","seychelles rupees":"SCR",
    "indonesian rupiah":"IDR","indonesian rupiahs":"IDR",
    "indonesia rupiah":"IDR",
    # ---- Pound variants ----
    "british pound":"GBP","british pounds":"GBP",
    "egyptian pound":"EGP","egyptian pounds":"EGP",
    "lebanese pound":"LBP","lebanese pounds":"LBP",
    "sudanese pound":"SDG","sudanese pounds":"SDG",
    "syrian pound":"SYP","syrian pounds":"SYP",
    # ---- Franc variants ----
    "swiss franc":"CHF","swiss francs":"CHF",
    "cfa franc":"XOF","west african franc":"XOF",
    "congolese franc":"CDF","congolese francs":"CDF",
    "rwandan franc":"RWF","rwandan francs":"RWF",
    "burundian franc":"BIF","burundian francs":"BIF",
    # ---- Dinar variants ----
    "kuwaiti dinar":"KWD","kuwait dinar":"KWD",
    "bahraini dinar":"BHD","bahrain dinar":"BHD",
    "iraqi dinar":"IQD","iraq dinar":"IQD",
    "jordanian dinar":"JOD","jordan dinar":"JOD",
    "libyan dinar":"LYD","libya dinar":"LYD",
    "tunisian dinar":"TND","tunisia dinar":"TND",
    "algerian dinar":"DZD","algeria dinar":"DZD",
    "serbian dinar":"RSD","serbia dinar":"RSD",
    # ---- Riyal/Rial variants ----
    "saudi riyal":"SAR","saudi riyals":"SAR",
    "qatari riyal":"QAR","qatar riyal":"QAR",
    "yemeni riyal":"YER","yemen riyal":"YER",
    "omani rial":"OMR","oman rial":"OMR",
    "iranian rial":"IRR","iran rial":"IRR",
    # ---- Krone/Krona variants ----
    "swedish krona":"SEK","sweden krona":"SEK",
    "norwegian krone":"NOK","norway krone":"NOK",
    "danish krone":"DKK","denmark krone":"DKK",
    "icelandic krona":"ISK","iceland krona":"ISK",
    "czech koruna":"CZK","czech republic koruna":"CZK",
    # ---- Peso variants ----
    "mexican peso":"MXN","mexico peso":"MXN",
    "argentine peso":"ARS","argentina peso":"ARS",
    "chilean peso":"CLP","chile peso":"CLP",
    "colombian peso":"COP","colombia peso":"COP",
    "philippine peso":"PHP","philippines peso":"PHP",
    "cuban peso":"CUP","cuba peso":"CUP",
    "dominican peso":"DOP","dominican republic peso":"DOP",
    "uruguayan peso":"UYU","uruguay peso":"UYU",
    # ---- Won variants ----
    "south korean won":"KRW","korean won":"KRW",
    "north korean won":"KPW","north korea won":"KPW",
    # ---- Other qualified ----
    "japanese yen":"JPY",
    "chinese yuan":"CNY","chinese renminbi":"CNY",
    "south african rand":"ZAR",
    "thai baht":"THB",
    "vietnamese dong":"VND",
    "emirati dirham":"AED","emirati dirhams":"AED",
    "turkish lira":"TRY",
    "russian ruble":"RUB","russian rubles":"RUB",
    "brazilian real":"BRL","brazilian reais":"BRL",
    "malaysian ringgit":"MYR",
    "philippine peso":"PHP","philippine pesos":"PHP",
    "bangladeshi taka":"BDT",
    "kenyan shilling":"KES","kenya shilling":"KES",
    "ugandan shilling":"UGX","uganda shilling":"UGX",
    "tanzanian shilling":"TZS","tanzania shilling":"TZS",
    "ethiopian birr":"ETB","ethiopia birr":"ETB",
    "ghanaian cedi":"GHS","ghana cedi":"GHS",
    "nigerian naira":"NGN","nigeria naira":"NGN",
}

# -------------------------
# Detection engine
# -------------------------

def build_code_pattern(rates):
    codes = sorted(rates.keys(), key=len, reverse=True)
    return '|'.join(re.escape(c) for c in codes)

def expand_abbreviated(text):
    """Convert abbreviated amounts to full numbers before detection.
    e.g. $2.3M → $2300000, ₹45L → ₹45000000, 1.5 billion dollars → 1500000000 dollars
    """
    word_mult = [
        (r'(\d+(?:\.\d+)?)\s*trillion', lambda m: str(int(float(m.group(1)) * 1_000_000_000_000))),
        (r'(\d+(?:\.\d+)?)\s*billion',  lambda m: str(int(float(m.group(1)) * 1_000_000_000))),
        (r'(\d+(?:\.\d+)?)\s*million',  lambda m: str(int(float(m.group(1)) * 1_000_000))),
        (r'(\d+(?:\.\d+)?)\s*thousand', lambda m: str(int(float(m.group(1)) * 1_000))),
        (r'(\d+(?:\.\d+)?)\s*lakh',     lambda m: str(int(float(m.group(1)) * 100_000))),
        (r'(\d+(?:\.\d+)?)\s*crore',    lambda m: str(int(float(m.group(1)) * 10_000_000))),
        (r'(\d+(?:\.\d+)?)\s*arab',     lambda m: str(int(float(m.group(1)) * 1_000_000_000))),
    ]
    for pattern, replacer in word_mult:
        text = re.sub(pattern, replacer, text, flags=re.IGNORECASE)

    suffix_map = {
        'T': 1_000_000_000_000,
        'B': 1_000_000_000,
        'M': 1_000_000,
        'K': 1_000,
        'L': 100_000,
        'CR': 10_000_000,
    }

    def replace_suffix(m):
        num    = float(m.group(1))
        suffix = m.group(2).upper()
        mult   = suffix_map.get(suffix, 1)
        return str(int(num * mult))

    text = re.sub(
        r'(\d+(?:\.\d+)?)\s*(CR|T|B|M|K|L)\b',
        replace_suffix,
        text,
        flags=re.IGNORECASE
    )

    return text

def find_pairs(text, unit_pat, flags=0):
    pairs = []
    for m in re.finditer(rf'(\d+(?:\.\d+)?)\s?({unit_pat})', text, flags):
        pairs.append((float(m.group(1)), m.group(2), m.start(), m.end()))
    for m in re.finditer(rf'({unit_pat})\s?(\d+(?:\.\d+)?)', text, flags):
        pairs.append((float(m.group(2)), m.group(1), m.start(), m.end()))
    return pairs

def process_message(msg, rates, base="USD"):
    bot_replies = []
    processed   = set()
    mentioned   = set()
    total_base  = 0.0

    CODE     = build_code_pattern(rates)
    SYM      = r'C\$|A\$|NZ\$|S\$|HK\$|MX\$|AR\$|R\$|د\.إ|\$|€|£|¥|₹|₽|₺|₩|₪|₫|₦|₲|₡|₴|₸|₼|₾|฿|﷼|kr|CHF|R'
    WORD_PAT = '|'.join(sorted(WORD_MAP.keys(), key=len, reverse=True))
    NAME_PAT = WORD_PAT

    base_sym    = next((s for s, c in SYMBOL_MAP.items() if c == base), "")
    base_prefix = f"{base_sym} " if base_sym else f"{base} "

    def convert(amount, currency):
        currency = currency.upper()
        if currency == base:
            return format_number(amount, base)
        if currency in rates and rates[currency] != 0:
            result = round(amount / rates[currency], 2)
            return format_number(result, base)
        return None

    def convert_raw(amount, currency):
        """Returns raw float for total accumulation."""
        currency = currency.upper()
        if currency == base:
            return amount
        if currency in rates and rates[currency] != 0:
            return round(amount / rates[currency], 2)
        return None

    def highlight(match):
        full = match.group(0)
        m1 = re.match(rf'(\d+(?:\.\d+)?)\s?({SYM})', full)
        m2 = re.match(rf'({SYM})\s?(\d+(?:\.\d+)?)', full)
        if m1:   amount, symbol = float(m1.group(1)), m1.group(2)
        elif m2: amount, symbol = float(m2.group(2)), m2.group(1)
        else:    return full
        currency  = SYMBOL_MAP.get(symbol)
        converted = convert(amount, currency) if currency else None
        if converted is not None:
            return (f'<span class="currency">{full}'
                    f'<span class="tooltip">{base_prefix}{converted}</span></span>')
        return full

    # Expand abbreviated amounts before detection
    expanded_msg = expand_abbreviated(msg)

    highlighted_msg = re.sub(
        rf'(?:(?:\d+(?:\.\d+)?)\s?(?:{SYM})|(?:{SYM})\s?(?:\d+(?:\.\d+)?))',
        highlight, expanded_msg
    )

    # Symbol pairs
    for amount, symbol, *_ in find_pairs(expanded_msg, SYM):
        currency = SYMBOL_MAP.get(symbol)
        key = f"{amount}_{currency}"
        if not currency or key in processed:
            continue
        converted = convert(amount, currency)
        if converted is None:
            continue
        raw = convert_raw(amount, currency)
        processed.add(key)
        total_base += raw
        bot_replies.append(f"{symbol}{amount} {currency} → {base_prefix}{converted}")

    # Word pairs
    for amount, word, *_ in find_pairs(expanded_msg, WORD_PAT, flags=re.IGNORECASE):
        currency = WORD_MAP.get(word.lower())
        key = f"{amount}_{currency}"
        if not currency or key in processed:
            continue
        converted = convert(amount, currency)
        if converted is None:
            continue
        raw = convert_raw(amount, currency)
        processed.add(key)
        total_base += raw
        bot_replies.append(f"{amount} {word} ({currency}) → {base_prefix}{converted}")

    # ISO code pairs
    for amount, code, *_ in find_pairs(expanded_msg, CODE, flags=re.IGNORECASE):
        code = code.upper()
        key  = f"{amount}_{code}"
        if key in processed or code not in rates:
            continue
        converted = convert(amount, code)
        if converted is None:
            continue
        raw = convert_raw(amount, code)
        processed.add(key)
        total_base += raw
        bot_replies.append(f"{amount} {code} → {base_prefix}{converted}")

    # Name-only mention
    if not processed:
        for m in re.finditer(rf'\b({NAME_PAT})\b', expanded_msg, re.IGNORECASE):
            name     = m.group(1).lower()
            currency = WORD_MAP.get(name)
            if not currency or currency in mentioned:
                continue
            converted = convert(1, currency)
            if converted is None:
                continue
            mentioned.add(currency)
            bot_replies.append(f"1 {currency} = {base_prefix}{converted}")

    if total_base > 0 and len(processed) > 1:
        bot_replies.append(f"Combined total ≈ {base_prefix}{format_number(round(total_base, 2), base)}")

    if not bot_replies:
        bot_replies.append(
            "I couldn't find any currency amounts in that message. "
            "Try something like <b>$100</b>, <b>50 euros</b>, <b>200 PKR</b>, "
            "or <b>What's the yen rate?</b>"
        )

    return highlighted_msg, bot_replies

# -------------------------
# Routes
# -------------------------

@app.route("/")
def chat():
    return render_template("chat.html")

@app.route("/currencies")
def currencies():
    rates = get_rates("USD")
    return jsonify(sorted(rates.keys()))

@app.route("/rate-age")
def rate_age():
    """Return how many minutes ago rates were last updated."""
    base = request.args.get("base", "USD").upper()
    sample = RateCache.query.filter_by(base=base).first()
    if not sample:
        return jsonify({"minutes": None})
    updated = aware(sample.updated_at)
    minutes = int((now_utc() - updated).total_seconds() / 60)
    return jsonify({"minutes": minutes})

@app.route("/history")
def history():
    messages = Message.query.order_by(Message.created_at).all()
    return jsonify([{
        "type":       m.msg_type,
        "content":    m.content,
        "created_at": m.created_at.strftime("%H:%M")
    } for m in messages])

@app.route("/send", methods=["POST"])
def send():
    data = request.json
    raw  = data.get("message", "").strip()
    # Sanitise — strip HTML tags to prevent XSS on public URL
    msg  = re.sub(r'<[^>]+>', '', raw).strip()
    base = data.get("base", "USD").upper()
    targets = data.get("targets", [])

    # Validate base currency against live rate list dynamically
    all_known = get_rates("USD")
    if base not in all_known and base != "USD":
        return jsonify([{
            "type": "bot",
            "content": f"⚠ <b>{base}</b> is not a recognised currency code. Try USD, EUR, INR, GBP etc.",
            "created_at": "--:--"
        }])

    if not msg:
        return jsonify([])

    rates = get_rates(base)
    if not rates:
        return jsonify([{
            "type": "bot",
            "content": "⚠ Could not fetch live exchange rates. Please check your internet connection and try again.",
            "created_at": "--:--"
        }])

    highlighted_msg, bot_replies = process_message(msg, rates, base)

    # Multi-target: group all target conversions into one bubble per amount
    if targets:
        # Rebuild a combined reply per detected amount
        combined = {}
        for target in targets:
            target = target.upper()
            if target == base:
                continue
            target_rates = get_rates(target)
            if not target_rates:
                continue
            _, target_replies = process_message(msg, target_rates, target)
            for reply in target_replies:
                if "couldn't find" not in reply and "Combined" not in reply:
                    # Extract the left side (e.g. "92.0 bangladeshi taka (BDT)")
                    if "→" in reply:
                        left, right = reply.split("→", 1)
                        key = left.strip()
                        if key not in combined:
                            combined[key] = []
                        combined[key].append(right.strip())

        # Merge with base replies
        merged = []
        for reply in bot_replies:
            if "→" in reply and "couldn't find" not in reply and "Combined" not in reply:
                left, right = reply.split("→", 1)
                key = left.strip()
                all_rights = [right.strip()]
                if key in combined:
                    all_rights += combined[key]
                merged.append(f"{key} →  " + "  |  ".join(all_rights))
            else:
                merged.append(reply)
        bot_replies = merged
    results = []

    user_msg = Message(msg_type="user", content=highlighted_msg)
    db.session.add(user_msg)
    db.session.flush()
    results.append({
        "type":       "user",
        "content":    highlighted_msg,
        "created_at": user_msg.created_at.strftime("%H:%M")
    })

    for reply in bot_replies:
        bot_msg = Message(msg_type="bot", content=reply)
        db.session.add(bot_msg)
        db.session.flush()
        results.append({
            "type":       "bot",
            "content":    reply,
            "created_at": bot_msg.created_at.strftime("%H:%M")
        })

    db.session.commit()
    return jsonify(results)

@app.route("/clear", methods=["POST"])
def clear():
    Message.query.delete()
    db.session.commit()
    return jsonify({"ok": True})

# -------------------------
# Init
# -------------------------

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    import webbrowser
    import threading
    def open_browser():
        import time
        time.sleep(1)
        webbrowser.get('windows-default').open("http://127.0.0.1:5001")
    threading.Thread(target=open_browser).start()
    app.run(debug=True, port=5001, use_reloader=False)