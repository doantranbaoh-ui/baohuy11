from flask import Flask, jsonify, request

app = Flask(__name__)
users = {}
balances = {}
daily = {}
jackpot = 100000

@app.route('/api/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/api/user', methods=['POST'])
def create_user():
    data = request.json
    uid = str(data['uid'])
    users[uid] = data['name']
    balances[uid] = data.get('initial_balance', 5000)
    return jsonify({"status": "success"})

@app.route('/api/balance/<int:uid>')
def get_balance(uid):
    bal = balances.get(str(uid), 5000)
    return jsonify({"balance": bal})

@app.route('/api/balance/add', methods=['POST'])
def add_balance():
    data = request.json
    uid = str(data['uid'])
    amount = data['amount']
    balances[uid] = balances.get(uid, 5000) + amount
    return jsonify({"new_balance": balances[uid]})

@app.route('/api/users')
def get_users():
    return jsonify({"users": users})

@app.route('/api/daily/check/<int:uid>')
def check_daily(uid):
    from datetime import date
    today = date.today().isoformat()
    claimed = daily.get(str(uid)) == today
    return jsonify({"claimed": claimed})

@app.route('/api/daily/claim', methods=['POST'])
def claim_daily():
    from datetime import date
    import random
    uid = str(request.json['uid'])
    today = date.today().isoformat()
    if daily.get(uid) == today:
        return jsonify({"reward": 0})
    daily[uid] = today
    reward = 500 + random.randint(0, 1000)
    balances[uid] = balances.get(uid, 5000) + reward
    return jsonify({"reward": reward})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
