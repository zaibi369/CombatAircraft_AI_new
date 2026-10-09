import json
import random
from decimal import Decimal
from datetime import datetime

ACCOUNTS_FILE = "accounts.json"
TRANSACTION_FILE = "transactions.json"


# =========================
# FILE HANDLING
# =========================

def load_accounts():
    try:
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)

    except FileNotFoundError:
        return {}

    except json.JSONDecodeError:
        raise ValueError("accounts.json is corrupted")


def save_accounts(accounts):
    try:
        with open(ACCOUNTS_FILE, "w") as f:
            json.dump(accounts, f, indent=4)

    except Exception as e:
        raise Exception(f"Failed saving accounts: {e}")


# =========================
# TRANSACTION LOGGER
# =========================

def log_transaction(
    tx_type,
    account_id,
    amount,
    fee,
    balance,
    receiver=None
):
    log = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": tx_type,
        "account_id": account_id,
        "receiver": receiver,
        "amount": str(amount),
        "fee": str(fee),
        "balance": str(balance)
    }

    try:
        with open(TRANSACTION_FILE, "a") as f:
            f.write(json.dumps(log) + "\n")

    except Exception as e:
        print(f"Log error: {e}")


# =========================
# HELPERS
# =========================

def validate_amount(amount, minimum=10):

    try:
        amount = Decimal(str(amount))

    except:
        raise ValueError("Amount must be a number")

    if amount < Decimal(str(minimum)):
        raise ValueError(
            f"Minimum amount is {minimum}"
        )

    return amount


def find_account(accounts, pin):

    pin = str(pin).strip()

    if pin in accounts:
        return pin

    return None


def find_balance(accounts, pin):

    pin = find_account(accounts, pin)

    if pin is None:
        raise ValueError("Account not found")

    return Decimal(str(accounts[pin]["balance"]))


# =========================
# PIN SYSTEM
# =========================

def make_pin(accounts):

    while True:

        option = input(
            "\n1. Manual PIN\n2. Random PIN\nChoose: "
        ).strip()

        if option == "1":

            while True:

                pin = input(
                    "Enter 4-digit PIN: "
                ).strip()

                if not pin.isdigit():
                    print("PIN must contain numbers only")
                    continue

                if len(pin) != 4:
                    print("PIN must be exactly 4 digits")
                    continue

                if pin in accounts:
                    print("PIN already exists")
                    continue

                return pin

        elif option == "2":

            while True:

                pin = str(
                    random.randint(1000, 9999)
                )

                if pin not in accounts:
                    print(f"Generated PIN: {pin}")

                    agree = input(
                        "Accept? (y/n): "
                    ).lower()

                    if agree == "y":
                        return pin

        else:
            print("Invalid option")


def pin_check(accounts):

    attempts = 3

    while attempts > 0:

        pin = input(
            "Enter your Master PIN: "
        ).strip()

        if pin in accounts:

            name = accounts[pin]["name"]

            print(
                f"\nAccess granted. Welcome back, {name}."
            )

            return pin

        attempts -= 1

        print(
            f"Invalid PIN. Attempts left: {attempts}"
        )

    return None


# =========================
# ACCOUNT CREATION
# =========================

def create_account():

    accounts = load_accounts()

    print("\n=== CREATE ACCOUNT ===")

    first = input("First name: ").strip().capitalize()
    last = input("Last name: ").strip().capitalize()

    name = f"{first} {last}"

    while True:

        option = input(
            "\n1. Personal\n2. Savings\n3. Checking\nChoose: "
        ).strip()

        types = {
            "1": "personal",
            "2": "savings",
            "3": "checking"
        }

        if option in types:
            account_type = types[option]
            break

        print("Invalid option")

    pin = make_pin(accounts)

    accounts[pin] = {
        "name": name,
        "account_type": account_type,
        "balance": "0.00"
    }

    save_accounts(accounts)

    print("\nAccount created successfully.")
    print(f"Your PIN is: {pin}")


# =========================
# DEPOSIT
# =========================

def deposit():

    accounts = load_accounts()

    pin = pin_check(accounts)

    if pin is None:
        return

    try:

        amount = validate_amount(
            input("Deposit amount: ")
        )

        fee = Decimal("2.00")

        final_amount = amount - fee

        balance = find_balance(accounts, pin)

        new_balance = balance + final_amount

        accounts[pin]["balance"] = str(new_balance)

        save_accounts(accounts)

        log_transaction(
            "deposit",
            pin,
            amount,
            fee,
            new_balance
        )

        print("\nDeposit successful")
        print(f"Fee: {fee}")
        print(f"New Balance: {new_balance}")

    except Exception as e:
        print(f"Error: {e}")


# =========================
# WITHDRAWAL
# =========================

def withdraw():

    accounts = load_accounts()

    pin = pin_check(accounts)

    if pin is None:
        return

    try:

        amount = validate_amount(
            input("Withdrawal amount: ")
        )

        fee = Decimal("3.00")

        balance = find_balance(accounts, pin)

        total = amount + fee

        if total > balance:
            print("Insufficient balance")
            return

        new_balance = balance - total

        accounts[pin]["balance"] = str(new_balance)

        save_accounts(accounts)

        log_transaction(
            "withdrawal",
            pin,
            amount,
            fee,
            new_balance
        )

        print("\nWithdrawal successful")
        print(f"Fee: {fee}")
        print(f"New Balance: {new_balance}")

    except Exception as e:
        print(f"Error: {e}")


# =========================
# TRANSFER
# =========================

def transfer():

    accounts = load_accounts()

    sender = pin_check(accounts)

    if sender is None:
        return

    receiver = input(
        "Enter receiver PIN: "
    ).strip()

    if sender == receiver:
        print("Cannot transfer to yourself")
        return

    if receiver not in accounts:
        print("Receiver not found")
        return

    try:

        amount = validate_amount(
            input("Transfer amount: ")
        )

        fee = Decimal("5.00")

        sender_balance = find_balance(
            accounts,
            sender
        )

        receiver_balance = find_balance(
            accounts,
            receiver
        )

        total = amount + fee

        if total > sender_balance:
            print("Insufficient funds")
            return

        new_sender_balance = (
            sender_balance - total
        )

        new_receiver_balance = (
            receiver_balance + amount
        )

        accounts[sender]["balance"] = str(
            new_sender_balance
        )

        accounts[receiver]["balance"] = str(
            new_receiver_balance
        )

        save_accounts(accounts)

        log_transaction(
            "transfer",
            sender,
            amount,
            fee,
            new_sender_balance,
            receiver
        )

        print("\nTransfer successful")
        print(
            f"Sender Balance: {new_sender_balance}"
        )
        print(
            f"Receiver Balance: {new_receiver_balance}"
        )

    except Exception as e:
        print(f"Error: {e}")


# =========================
# CHECK BALANCE
# =========================

def check_balance():

    accounts = load_accounts()

    pin = pin_check(accounts)

    if pin is None:
        return

    balance = find_balance(accounts, pin)

    print(f"\nCurrent Balance: {balance}")


# =========================
# ACCOUNT DETAILS
# =========================

def account_details():

    accounts = load_accounts()

    pin = pin_check(accounts)

    if pin is None:
        return

    user = accounts[pin]

    print("\n========================")
    print("ACCOUNT DETAILS")
    print("========================")

    print(f"PIN: {pin}")
    print(f"Name: {user['name']}")
    print(f"Type: {user['account_type']}")
    print(f"Balance: {user['balance']}")

    print("========================")


# =========================
# MAIN MENU
# =========================

def main():

    while True:

        print("\n========== OCTAVIAN BANK ==========")

        print("1. Create Account")
        print("2. Deposit")
        print("3. Withdraw")
        print("4. Transfer")
        print("5. Check Balance")
        print("6. Account Details")
        print("7. Exit")

        choice = input("\nChoose: ").strip()

        if choice == "1":
            create_account()

        elif choice == "2":
            deposit()

        elif choice == "3":
            withdraw()

        elif choice == "4":
            transfer()

        elif choice == "5":
            check_balance()

        elif choice == "6":
            account_details()

        elif choice == "7":
            print("\nThank you for using OCTAVIAN BANK.")
            break

        else:
            print("Invalid choice")


# =========================
# START
# =========================

if __name__ == "__main__":
    main()