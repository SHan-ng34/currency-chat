# Currency Chat 💱

A conversational currency converter that understands how people naturally write about money.

Instead of requiring users to select currencies and enter amounts into separate fields, Currency Chat lets users type monetary references in natural language and converts them into a chosen base currency.

**[🚀 Live Demo](https://currency-chat.onrender.com/)** · **[💻 GitHub](https://github.com/SHan-ng34/currency-chat)**

## Problem

People frequently encounter international monetary values while reading articles, comparing prices, planning trips, or discussing expenses.

Typical currency converters require users to stop, identify the currency, enter the amount, and perform the conversion separately.

Currency Chat explores a more natural interaction: **type the monetary reference as you would normally write it, and let the application interpret it.**

## What It Can Understand

Examples:

```text
$200 and €150 on my trip
```

Detects both currencies and calculates their combined value.

```text
50 crore rupees
```

Understands Indian numbering conventions.

```text
92 bangladeshi taka
```

Uses country-qualified currency names.

```text
What's the yen rate?
```

Returns the current exchange rate without requiring an amount.

It also supports:

* Currency symbols
* ISO currency codes
* Currency names
* Country-qualified currency names
* Abbreviated values such as `$2.3M` and `€1.5B`
* Multiple currencies in a single message
* 160+ currencies
* Any supported currency as the base currency

## Key Features

* **Natural-language currency detection** using a custom regex-based parsing engine
* **Live exchange rates** through an external exchange-rate API
* **Rate caching** to reduce repeated API requests
* **Multi-currency conversion** within a single message
* **Indian numbering support** including lakh and crore
* **Chat history persistence** using SQLite
* **AJAX-based interaction** without full-page reloads
* **Publicly deployed Flask web application**

## How It Works

```text
User message
     ↓
Currency & amount detection
     ↓
Natural-language parsing
     ↓
Currency identification
     ↓
Exchange-rate lookup
     ↓
Cached rate / live API
     ↓
Conversion & aggregation
     ↓
Formatted response
```

The application combines pattern-based parsing with currency metadata to interpret different ways people write monetary values.

## Tech Stack

**Backend**

* Python
* Flask
* Flask-SQLAlchemy

**Frontend**

* HTML
* CSS
* JavaScript
* AJAX

**Data & APIs**

* SQLite
* Exchange-rate API
* Cached exchange rates

**Deployment**

* WSGI-based Flask deployment

## Project Structure

```text
currency-chat/
├── Templates/
│   └── Chat.html
├── instance/
├── .gitignore
├── App.py
├── Procfile
├── Requirements.txt
└── wsgi.py
```

The SQLite database is generated locally and is excluded from version control.

## Example Interaction

**User:**

> $200 and €150 on my trip

**Currency Chat:**

Identifies both monetary values, converts them using current exchange rates, and returns their combined value in the selected base currency.

The application can also interpret values such as:

> 2.3 million dollars

> 50 crore rupees

> 92 Bangladeshi taka

without requiring users to manually select the currency first.

## Why This Project?

The project was built to explore a product question:

> **Can currency conversion become an interaction problem rather than a form-filling problem?**

The current version focuses on the conversational web experience. A future product direction could extend the same parsing capability into a browser extension that detects monetary values directly on webpages.

## Limitations

* Exchange rates depend on the external API and its availability.
* Currency symbols can be ambiguous in some contexts and may require additional textual context.
* The parser is rule-based rather than powered by a large language model.
* Cached rates may be used when a fresh API response is temporarily unavailable.

## Future Direction

The underlying currency-detection capability could be extended into a browser experience that automatically detects monetary values on webpages and provides contextual conversions without requiring users to leave the page.

---

Built with Python, Flask, JavaScript, and exchange-rate APIs.
