from __future__ import annotations

from collections import UserDict
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple


# =========================
# Моделі адресної книги (ООП)
# =========================

class Field:
    """Базове поле запису."""
    def __init__(self, value: str):
        self.value: str = value

    def __str__(self) -> str:
        return self.value


class Name(Field):
    """Ім'я контакту (обов'язкове поле)."""
    pass


class Phone(Field):
    """Телефон (рівно 10 цифр)."""
    def __init__(self, value: str):
        if not (value.isdigit() and len(value) == 10):
            raise ValueError("Phone number must contain exactly 10 digits.")
        super().__init__(value)


class Birthday(Field):
    """День народження у форматі DD.MM.YYYY."""
    def __init__(self, value: str):
        try:
            self.date_value: date = datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        super().__init__(value)


class Record:
    """Запис контакту: ім'я, телефони, (опційно) день народження."""
    def __init__(self, name: str):
        self.name: Name = Name(name)
        self.phones: List[Phone] = []
        self.birthday: Optional[Birthday] = None

    def add_phone(self, phone: str) -> None:
        self.phones.append(Phone(phone))

    def find_phone(self, phone: str) -> Optional[Phone]:
        for p in self.phones:
            if p.value == phone:
                return p
        return None

    def remove_phone(self, phone: str) -> None:
        p = self.find_phone(phone)
        if p is None:
            raise KeyError("Phone not found.")
        self.phones.remove(p)

    def edit_phone(self, old_phone: str, new_phone: str) -> None:
        p = self.find_phone(old_phone)
        if p is None:
            raise KeyError("Phone not found.")
        p.value = Phone(new_phone).value  # валідація нового номера

    def add_birthday(self, birthday: str) -> None:
        self.birthday = Birthday(birthday)

    def __str__(self) -> str:
        phones_str: str = "; ".join(p.value for p in self.phones) if self.phones else "—"
        bday_str: str = self.birthday.value if self.birthday else "—"
        return f"Contact name: {self.name.value}, phones: {phones_str}, birthday: {bday_str}"

from datetime import date

def _birthday_in_year(bday: date, year: int) -> date:
    """Повертає день народження в заданому році (29.02 -> 28.02 у невисокосний рік)."""
    try:
        return bday.replace(year=year)
    except ValueError:
        # Виникає, коли bday == 29.02, а рік не високосний
        return date(year, 2, 28)

class AddressBook(UserDict):
    """Адресна книга: зберігає записи (Record) та керує ними."""
    data: Dict[str, Record]

    def add_record(self, record: Record) -> None:
        self.data[record.name.value] = record

    def find(self, name: str) -> Optional[Record]:
        return self.data.get(name)

    def delete(self, name: str) -> None:
        if name not in self.data:
            raise KeyError("Contact not found.")
        del self.data[name]

    def get_upcoming_birthdays(self) -> List[Dict[str, str]]:
        """
        Повертає список привітань на наступні 7 днів.
        Якщо ДН у суботу/неділю — переносимо привітання на понеділок.
        Формат елементів: {"name": "...", "congratulation_date": "YYYY-MM-DD"}
        """
        today: date = date.today()
        end_date: date = today + timedelta(days=7)
        result: List[Dict[str, str]] = []

        for record in self.data.values():
            if record.birthday is None:
                continue

            bday: date = record.birthday.date_value
            bday_this_year: date = bday.replace(year=today.year)
            if bday_this_year < today:
                bday_this_year = bday_this_year.replace(year=today.year + 1)

            if today <= bday_this_year <= end_date:
                congrats: date = bday_this_year
                if congrats.weekday() == 5:      # субота
                    congrats += timedelta(days=2)
                elif congrats.weekday() == 6:    # неділя
                    congrats += timedelta(days=1)

                result.append(
                    {"name": record.name.value, "congratulation_date": congrats.isoformat()}
                )

        result.sort(key=lambda x: x["congratulation_date"])
        return result


# =========================
# CLI (парсер, декоратор, хендлери)
# =========================

Handler = Callable[..., str]


def parse_input(user_input: str) -> Tuple[str, List[str]]:
    """Повертає (command, args). Команда нечутлива до регістру."""
    parts: List[str] = user_input.strip().split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


def input_error(func: Handler) -> Handler:
    """
    Декоратор для обробки помилок введення:
    KeyError, ValueError, IndexError -> повертаємо повідомлення, програму не зупиняємо.
    """
    def inner(*args: Any, **kwargs: Any) -> str:
        try:
            return func(*args, **kwargs)

        except IndexError:
            name = func.__name__
            if name == "add_contact":
                return "Give me name and phone please."
            if name == "change_contact":
                return "Give me name, old phone and new phone please."
            if name in ("show_phone", "show_birthday"):
                return "Enter user name."
            if name == "add_birthday":
                return "Give me name and birthday (DD.MM.YYYY) please."
            return "Not enough arguments."

        except ValueError as e:
            return str(e)

        except KeyError as e:
            msg = str(e).strip("'")
            return msg if msg else "Contact not found."

    return inner


@input_error
def add_contact(args: List[str], book: AddressBook) -> str:
    """add [ім'я] [телефон]"""
    name: str = args[0]
    phone: str = args[1]

    record: Optional[Record] = book.find(name)
    if record is None:
        # Щоб не створити "порожній" контакт при невалідному телефоні — валідую до додавання в book
        new_record = Record(name)
        new_record.add_phone(phone)  # може кинути ValueError
        book.add_record(new_record)
        return "Contact added."

    record.add_phone(phone)          # може кинути ValueError
    return "Contact updated."


@input_error
def change_contact(args: List[str], book: AddressBook) -> str:
    """change [ім'я] [старий телефон] [новий телефон]"""
    name: str = args[0]
    old_phone: str = args[1]
    new_phone: str = args[2]

    record: Optional[Record] = book.find(name)
    if record is None:
        raise KeyError("Contact not found.")

    record.edit_phone(old_phone, new_phone)  # може кинути KeyError("Phone not found.")
    return "Contact updated."


@input_error
def show_phone(args: List[str], book: AddressBook) -> str:
    """phone [ім'я]"""
    name: str = args[0]
    record: Optional[Record] = book.find(name)
    if record is None:
        raise KeyError("Contact not found.")
    if not record.phones:
        return "No phones for this contact."
    return "; ".join(p.value for p in record.phones)


@input_error
def show_all(_: List[str], book: AddressBook) -> str:
    """all"""
    if not book.data:
        return "No contacts."
    return "\n".join(str(r) for r in book.data.values())


@input_error
def add_birthday(args: List[str], book: AddressBook) -> str:
    """add-birthday [ім'я] [DD.MM.YYYY]"""
    name: str = args[0]
    bday: str = args[1]

    record: Optional[Record] = book.find(name)
    if record is None:
        raise KeyError("Contact not found.")

    record.add_birthday(bday)  # може кинути ValueError
    return "Birthday added."


@input_error
def show_birthday(args: List[str], book: AddressBook) -> str:
    """show-birthday [ім'я]"""
    name: str = args[0]
    record: Optional[Record] = book.find(name)
    if record is None:
        raise KeyError("Contact not found.")
    if record.birthday is None:
        return "Birthday is not set."
    return record.birthday.value


@input_error
def birthdays(_: List[str], book: AddressBook) -> str:
    """birthdays"""
    items: List[Dict[str, str]] = book.get_upcoming_birthdays()
    if not items:
        return "No birthdays in the next 7 days."
    lines: List[str] = ["Upcoming birthdays:"]
    for it in items:
        lines.append(f"{it['name']}: {it['congratulation_date']}")
    return "\n".join(lines)


def main() -> None:
    """Головний цикл бота. Усі input/print — тут."""
    book = AddressBook()
    print("Welcome to the assistant bot!")

    while True:
        try:
            user_input: str = input("Enter a command: ")
        except (KeyboardInterrupt, EOFError):
            print("\nGood bye!")
            break

        command, args = parse_input(user_input)

        if command in ("close", "exit"):
            print("Good bye!")
            break

        if command == "":
            continue

        if command == "hello":
            print("How can I help you?")

        elif command == "add":
            print(add_contact(args, book))

        elif command == "change":
            print(change_contact(args, book))

        elif command == "phone":
            print(show_phone(args, book))

        elif command == "all":
            print(show_all(args, book))

        elif command == "add-birthday":
            print(add_birthday(args, book))

        elif command == "show-birthday":
            print(show_birthday(args, book))

        elif command == "birthdays":
            print(birthdays(args, book))

        else:
            print("Invalid command.")


if __name__ == "__main__":
    main()