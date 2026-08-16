"""
مدير الميزانية الشخصية (Personal Budget Manager)
تطبيق Flet + SQLite لإدارة الدخل والمصاريف الشخصية، مع صفحة "الحساب الادخاري
والتخطيط الذكي" لتحديد أهداف ادخارية وتحليلها تلقائياً.

التشغيل على الكمبيوتر:
    pip install flet
    flet run main.py

بناء APK للأندرويد:
    flet build apk
"""

import sqlite3
import flet as ft

# --------------------------------------------------------------------------
# إعدادات عامة وثوابت
# --------------------------------------------------------------------------

DB_NAME = "budget.db"

CAT_ESSENTIAL = "أساسي / ضروري"
CAT_LUXURY = "كمالي / ثانوي"

BG_COLOR = "#0E1A2B"
CARD_BG = "#16233A"
FIELD_BG = "#1C2C46"

INCOME_COLOR = ft.Colors.BLUE_400
EXPENSE_COLOR = ft.Colors.ORANGE_400
POSITIVE_COLOR = ft.Colors.GREEN_400
NEGATIVE_COLOR = ft.Colors.RED_400
SUGGESTION_COLOR = ft.Colors.AMBER_400
SAVINGS_COLOR = ft.Colors.PURPLE_300
NEUTRAL_COLOR = ft.Colors.BLUE_GREY_400

# حدود نسبة الادخار "الصحية" الموصى بها من إجمالي الدخل الشهري
MIN_SAVINGS_RATE = 10.0
MAX_SAVINGS_RATE = 30.0


# --------------------------------------------------------------------------
# طبقة قاعدة البيانات (SQLite)
# --------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """يفتح اتصالاً جديداً بقاعدة بيانات SQLite المحلية."""
    return sqlite3.connect(DB_NAME)


def init_db() -> None:
    """ينشئ جميع الجداول المطلوبة إن لم تكن موجودة، ويضبط القيم الافتراضية."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            income REAL NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute("INSERT OR IGNORE INTO settings (id, income) VALUES (1, 0)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL
        )
        """
    )

    # جدول أهداف الادخار: كل هدف محفوظ بنتائج المحاكاة الخاصة به
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS savings_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            duration_months INTEGER NOT NULL,
            monthly_savings_rate REAL NOT NULL,
            account_identifier TEXT
        )
        """
    )

    # جدول الحساب الادخاري المرتبط (صف واحد ثابت، بنفس نمط جدول settings)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS savings_account (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            account_identifier TEXT NOT NULL DEFAULT ''
        )
        """
    )
    cur.execute(
        "INSERT OR IGNORE INTO savings_account (id, account_identifier) VALUES (1, '')"
    )

    conn.commit()
    conn.close()


def db_get_income() -> float:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT income FROM settings WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else 0.0


def db_set_income(value: float) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE settings SET income = ? WHERE id = 1", (value,))
    conn.commit()
    conn.close()


def db_add_expense(name: str, amount: float, category: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO expenses (name, amount, category) VALUES (?, ?, ?)",
        (name, amount, category),
    )
    conn.commit()
    conn.close()


def db_delete_expense(expense_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()


def db_clear_expenses() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses")
    conn.commit()
    conn.close()


def db_get_expenses() -> list[tuple[int, str, float, str]]:
    """يعيد المصاريف مرتّبة: الأساسي/الضروري أولاً ثم الكمالي/الثانوي."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, amount, category
        FROM expenses
        ORDER BY CASE WHEN category = ? THEN 0 ELSE 1 END, id ASC
        """,
        (CAT_ESSENTIAL,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def db_get_total_expenses() -> float:
    """يعيد إجمالي المصاريف مباشرة من قاعدة البيانات (تُستخدم من صفحة الادخار)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else 0.0


def db_get_account_identifier() -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT account_identifier FROM savings_account WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""


def db_set_account_identifier(value: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE savings_account SET account_identifier = ? WHERE id = 1", (value,)
    )
    conn.commit()
    conn.close()


def db_add_savings_goal(
    goal_name: str,
    target_amount: float,
    duration_months: int,
    monthly_savings_rate: float,
    account_identifier: str,
) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO savings_goals
            (goal_name, target_amount, duration_months, monthly_savings_rate, account_identifier)
        VALUES (?, ?, ?, ?, ?)
        """,
        (goal_name, target_amount, duration_months, monthly_savings_rate, account_identifier),
    )
    conn.commit()
    conn.close()


def db_get_savings_goals() -> list[tuple[int, str, float, int, float, str]]:
    """يعيد الأهداف الادخارية المحفوظة، الأحدث أولاً."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, goal_name, target_amount, duration_months, monthly_savings_rate, account_identifier
        FROM savings_goals
        ORDER BY id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def db_delete_savings_goal(goal_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM savings_goals WHERE id = ?", (goal_id,))
    conn.commit()
    conn.close()


def db_clear_savings_goals() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM savings_goals")
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# دوال مساعدة
# --------------------------------------------------------------------------

def parse_amount(text: str, allow_zero: bool = True) -> float | None:
    """يحاول تحويل النص إلى رقم عشري صحيح؛ يعيد None عند الفشل."""
    if text is None:
        return None
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    if allow_zero:
        if value < 0:
            return None
    else:
        if value <= 0:
            return None
    return value


def parse_positive_int(text: str) -> int | None:
    """يحاول تحويل النص إلى عدد صحيح موجب (يُستخدم لمدة الهدف بالأشهر)."""
    if text is None:
        return None
    try:
        value = int(str(text).strip())
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def fmt(value: float) -> str:
    return f"{value:.2f}"


# --------------------------------------------------------------------------
# محرّك التحليل المالي الذكي لخطة الادخار
# --------------------------------------------------------------------------

def analyze_savings_goal(
    income: float,
    remaining_before: float,
    target_amount: float,
    duration_months: int,
) -> dict:
    """
    يحسب القسط الشهري المطلوب لتحقيق الهدف، ونسبته من إجمالي الدخل، ثم يصنّف
    الهدف ضمن إحدى ثلاث حالات مع رسالة توصية مناسبة:
        - "over"  : استقطاع مرتفع جداً / غير واقعي.
        - "under" : القدرة المالية تسمح بتسريع الادخار.
        - "ok"    : هدف واقعي ومغطّى ضمن النطاق الصحي (10% - 30%).
        - "no_income" : لا يوجد دخل مسجّل بعد لإجراء الحساب.
    """
    if income <= 0:
        return {
            "monthly_installment": 0.0,
            "rate_percent": 0.0,
            "remaining_after": remaining_before,
            "status": "no_income",
            "message": "الرجاء تسجيل دخلك الشهري من الشاشة الرئيسية أولاً لحساب خطة الادخار.",
        }

    monthly_installment = target_amount / duration_months
    rate_percent = (monthly_installment / income) * 100
    remaining_after = remaining_before - monthly_installment

    if monthly_installment > remaining_before or rate_percent > MAX_SAVINGS_RATE:
        status = "over"
        message = (
            "هدفك يتطلب استقطاعاً عالياً يضغط ميزانيتك. يُفضل تمديد فترة الوصول "
            "للهدف أو تقليل المبلغ المطلوب لتسهيل الادخار."
        )
    elif rate_percent < MIN_SAVINGS_RATE and remaining_before >= income * (MIN_SAVINGS_RATE / 100):
        status = "under"
        message = (
            "قدرتك المالية تسمح لك بتحقيق هذا الهدف بفترة أقصر من خلال زيادة نسبة "
            "الادخار دون التأثير على مصاريفك الأساسية."
        )
    else:
        status = "ok"
        message = "🎯 هدف واقعي! نسبة ادخارك ضمن النطاق الصحي (10% - 30%) ومغطاة من فائضك الشهري."

    return {
        "monthly_installment": monthly_installment,
        "rate_percent": rate_percent,
        "remaining_after": remaining_after,
        "status": status,
        "message": message,
    }


STATUS_COLOR = {
    "over": NEGATIVE_COLOR,
    "under": SUGGESTION_COLOR,
    "ok": POSITIVE_COLOR,
    "no_income": NEUTRAL_COLOR,
}

STATUS_ICON = {
    "over": ft.Icons.WARNING_AMBER_OUTLINED,
    "under": ft.Icons.TRENDING_UP,
    "ok": ft.Icons.CHECK_CIRCLE_OUTLINE,
    "no_income": ft.Icons.INFO_OUTLINE,
}


# --------------------------------------------------------------------------
# التطبيق
# --------------------------------------------------------------------------

def main(page: ft.Page) -> None:
    page.title = "مدير الميزانية الشخصية"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_COLOR
    page.padding = 0
    page.window.width = 420
    page.window.height = 860
    page.scroll = ft.ScrollMode.HIDDEN

    init_db()

    def show_message(message: str, color: str) -> None:
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=color,
            )
        )

    def summary_card(title: str, value_control: ft.Text, color: str, icon: str) -> ft.Container:
        return ft.Container(
            expand=True,
            padding=14,
            border_radius=16,
            bgcolor=ft.Colors.with_opacity(0.12, color),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
                controls=[
                    ft.Icon(icon, color=color, size=20),
                    ft.Text(title, size=12, color=color, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
                    value_control,
                ],
            ),
        )

    # =================================================================
    # ============ الشاشة الرئيسية: الدخل والمصاريف =====================
    # =================================================================

    # ---------------------------------------------------------------
    # عناصر ملخص الميزانية (3 بطاقات)
    # ---------------------------------------------------------------

    income_value_text = ft.Text("0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    expenses_value_text = ft.Text("0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    remaining_value_text = ft.Text("0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

    income_card = summary_card("الدخل", income_value_text, INCOME_COLOR, ft.Icons.PAYMENTS_OUTLINED)
    expenses_card = summary_card("إجمالي المصاريف", expenses_value_text, EXPENSE_COLOR, ft.Icons.SHOPPING_BAG_OUTLINED)
    remaining_card = summary_card("المتبقي", remaining_value_text, POSITIVE_COLOR, ft.Icons.SAVINGS_OUTLINED)

    summary_row = ft.Row(
        controls=[income_card, expenses_card, remaining_card],
        spacing=10,
    )

    # ---------------------------------------------------------------
    # قسم إدخال الدخل
    # ---------------------------------------------------------------

    income_field = ft.TextField(
        label="الدخل الشهري / الراتب",
        value=fmt(db_get_income()),
        keyboard_type=ft.KeyboardType.NUMBER,
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    def handle_save_income(e: ft.Event) -> None:
        value = parse_amount(income_field.value, allow_zero=True)
        if value is None:
            show_message("⚠️ الرجاء إدخال رقم صحيح للدخل.", NEGATIVE_COLOR)
            return
        db_set_income(value)
        income_field.value = fmt(value)
        refresh_ui()
        show_message("✅ تم حفظ الدخل بنجاح.", POSITIVE_COLOR)

    save_income_button = ft.Button(
        content="حفظ / تحديث الدخل",
        icon=ft.Icons.SAVE_OUTLINED,
        on_click=handle_save_income,
        style=ft.ButtonStyle(
            bgcolor=INCOME_COLOR,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    income_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("أدخل الدخل الشهري", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                income_field,
                save_income_button,
            ],
        ),
    )

    # ---------------------------------------------------------------
    # قسم إضافة مصروف
    # ---------------------------------------------------------------

    expense_name_field = ft.TextField(
        label="اسم المصروف",
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    expense_amount_field = ft.TextField(
        label="القيمة",
        keyboard_type=ft.KeyboardType.NUMBER,
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    expense_category_dropdown = ft.Dropdown(
        label="التصنيف",
        value=CAT_ESSENTIAL,
        options=[
            ft.DropdownOption(key=CAT_ESSENTIAL, text=CAT_ESSENTIAL),
            ft.DropdownOption(key=CAT_LUXURY, text=CAT_LUXURY),
        ],
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
    )

    def handle_add_expense(e: ft.Event) -> None:
        name = (expense_name_field.value or "").strip()
        amount = parse_amount(expense_amount_field.value, allow_zero=False)
        category = expense_category_dropdown.value

        if not name:
            show_message("⚠️ الرجاء إدخال اسم المصروف.", NEGATIVE_COLOR)
            return
        if amount is None:
            show_message("⚠️ الرجاء إدخال قيمة رقمية موجبة صحيحة.", NEGATIVE_COLOR)
            return
        if category not in (CAT_ESSENTIAL, CAT_LUXURY):
            show_message("⚠️ الرجاء اختيار تصنيف المصروف.", NEGATIVE_COLOR)
            return

        db_add_expense(name, amount, category)

        expense_name_field.value = ""
        expense_amount_field.value = ""
        expense_category_dropdown.value = CAT_ESSENTIAL

        refresh_ui()
        show_message("✅ تمت إضافة المصروف بنجاح.", POSITIVE_COLOR)

    add_expense_button = ft.Button(
        content="➕ إضافة المصروف",
        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
        on_click=handle_add_expense,
        style=ft.ButtonStyle(
            bgcolor=EXPENSE_COLOR,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    add_expense_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("أضف مصروفاً", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                expense_name_field,
                expense_amount_field,
                expense_category_dropdown,
                add_expense_button,
            ],
        ),
    )

    # ---------------------------------------------------------------
    # قسم قائمة المصاريف
    # ---------------------------------------------------------------

    expenses_list_column = ft.Column(spacing=8)

    def handle_delete_expense(expense_id: int) -> None:
        db_delete_expense(expense_id)
        refresh_ui()
        show_message("🗑 تم حذف المصروف.", ft.Colors.BLUE_GREY_400)

    def build_expense_row(expense_id: int, name: str, amount: float, category: str) -> ft.Container:
        is_essential = category == CAT_ESSENTIAL
        tag_color = ft.Colors.TEAL_300 if is_essential else SUGGESTION_COLOR

        return ft.Container(
            padding=12,
            border_radius=12,
            bgcolor=FIELD_BG,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=4,
                        expand=True,
                        controls=[
                            ft.Text(name, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=20,
                                bgcolor=ft.Colors.with_opacity(0.18, tag_color),
                                content=ft.Text(category, size=11, color=tag_color, weight=ft.FontWeight.W_600),
                            ),
                        ],
                    ),
                    ft.Text(fmt(amount), size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=NEGATIVE_COLOR,
                        tooltip="حذف",
                        on_click=lambda e, eid=expense_id: handle_delete_expense(eid),
                    ),
                ],
            ),
        )

    empty_expenses_text = ft.Text(
        "لا توجد مصاريف مسجّلة بعد.",
        size=13,
        color=ft.Colors.BLUE_GREY_300,
        text_align=ft.TextAlign.CENTER,
    )

    def handle_clear_all_confirmed(e: ft.Event) -> None:
        db_clear_expenses()
        page.pop_dialog()
        refresh_ui()
        show_message("🗑 تم مسح جميع المصاريف.", ft.Colors.BLUE_GREY_400)

    def handle_clear_all_cancelled(e: ft.Event) -> None:
        page.pop_dialog()

    def handle_clear_all_click(e: ft.Event) -> None:
        # يُبنى الحوار من جديد في كل مرة لتفادي إعادة استخدام نفس الكائن
        # قبل أن تكتمل دورة إغلاقه في الواجهة.
        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("تأكيد المسح"),
            content=ft.Text("هل أنت متأكد من مسح جميع المصاريف؟ لا يمكن التراجع عن هذا الإجراء."),
            actions=[
                ft.Button(
                    content="نعم، امسح الكل",
                    on_click=handle_clear_all_confirmed,
                    style=ft.ButtonStyle(bgcolor=NEGATIVE_COLOR, color=ft.Colors.WHITE),
                ),
                ft.OutlinedButton(content="إلغاء", on_click=handle_clear_all_cancelled),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(confirm_dialog)

    clear_all_button = ft.Button(
        content="مسح كل المصاريف",
        icon=ft.Icons.DELETE_SWEEP_OUTLINED,
        on_click=handle_clear_all_click,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.with_opacity(0.15, NEGATIVE_COLOR),
            color=NEGATIVE_COLOR,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    expenses_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("المصاريف مرتبة حسب الأولوية", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                expenses_list_column,
                clear_all_button,
            ],
        ),
    )

    # ---------------------------------------------------------------
    # شريط التوصية الذكية
    # ---------------------------------------------------------------

    suggestion_text = ft.Text(
        "",
        size=13,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_600,
    )

    suggestion_bar = ft.Container(
        padding=14,
        border_radius=14,
        bgcolor=ft.Colors.with_opacity(0.15, SUGGESTION_COLOR),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=SUGGESTION_COLOR),
                ft.Container(content=suggestion_text, expand=True),
            ],
        ),
    )

    # ---------------------------------------------------------------
    # منطق تحديث الواجهة الرئيسية بالكامل
    # ---------------------------------------------------------------

    def refresh_ui() -> None:
        income = db_get_income()
        expenses = db_get_expenses()
        total_expenses = sum(row[2] for row in expenses)
        remaining = income - total_expenses

        income_value_text.value = fmt(income)
        expenses_value_text.value = fmt(total_expenses)
        remaining_value_text.value = fmt(remaining)

        if remaining >= 0:
            remaining_value_text.color = ft.Colors.WHITE
            remaining_card.bgcolor = ft.Colors.with_opacity(0.12, POSITIVE_COLOR)
            remaining_card.content.controls[0].color = POSITIVE_COLOR
            remaining_card.content.controls[1].color = POSITIVE_COLOR
        else:
            remaining_card.bgcolor = ft.Colors.with_opacity(0.12, NEGATIVE_COLOR)
            remaining_card.content.controls[0].color = NEGATIVE_COLOR
            remaining_card.content.controls[1].color = NEGATIVE_COLOR

        expenses_list_column.controls.clear()
        if expenses:
            for expense_id, name, amount, category in expenses:
                expenses_list_column.controls.append(
                    build_expense_row(expense_id, name, amount, category)
                )
        else:
            expenses_list_column.controls.append(empty_expenses_text)

        luxury_expenses = [row for row in expenses if row[3] == CAT_LUXURY]
        if luxury_expenses:
            biggest = max(luxury_expenses, key=lambda row: row[2])
            suggestion_text.value = (
                f"راجع «{biggest[1]}» لأنها أكبر مصروف كمالي (بقيمة {fmt(biggest[2])} دينار)."
            )
        elif remaining < 0:
            suggestion_text.value = "مصاريفك تجاوزت دخلك، راجع البنود الأساسية لتقليل العجز."
        else:
            suggestion_text.value = "لا توجد مصاريف كمالية حالياً، استمر في هذا الأداء الرائع للادخار!"

        page.update()

    # ---------------------------------------------------------------
    # تركيب واجهة الشاشة الرئيسية
    # ---------------------------------------------------------------

    home_header = ft.Container(
        padding=ft.Padding.only(top=20, bottom=10, left=20, right=20),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color=INCOME_COLOR, size=28),
                        ft.Text("مدير الميزانية الشخصية", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.SAVINGS_OUTLINED,
                    icon_color=SAVINGS_COLOR,
                    tooltip="الحساب الادخاري والتخطيط الذكي",
                    on_click=lambda e: show_savings_view(),
                ),
            ],
        ),
    )

    home_body = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=16,
        controls=[
            home_header,
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=20),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        summary_row,
                        income_section,
                        add_expense_section,
                        expenses_section,
                        suggestion_bar,
                        ft.Container(height=20),
                    ],
                ),
            ),
        ],
    )

    # =================================================================
    # ======== صفحة الادخار: الحساب الادخاري والتخطيط الذكي =============
    # =================================================================

    # ---------------------------------------------------------------
    # بطاقات ملخص سريعة (الدخل / المصاريف / المتبقي قبل وبعد الادخار)
    # ---------------------------------------------------------------

    sv_income_text = ft.Text("0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    sv_expenses_text = ft.Text("0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    sv_remaining_before_text = ft.Text("0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    sv_remaining_after_text = ft.Text("0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

    sv_income_card = summary_card("الدخل الكلي", sv_income_text, INCOME_COLOR, ft.Icons.PAYMENTS_OUTLINED)
    sv_expenses_card = summary_card("إجمالي المصاريف", sv_expenses_text, EXPENSE_COLOR, ft.Icons.SHOPPING_BAG_OUTLINED)
    sv_remaining_before_card = summary_card(
        "المتبقي قبل الادخار", sv_remaining_before_text, POSITIVE_COLOR, ft.Icons.ACCOUNT_BALANCE_OUTLINED
    )
    sv_remaining_after_card = summary_card(
        "المتبقي بعد الادخار", sv_remaining_after_text, SAVINGS_COLOR, ft.Icons.SAVINGS_OUTLINED
    )

    sv_summary_row_1 = ft.Row(controls=[sv_income_card, sv_expenses_card], spacing=10)
    sv_summary_row_2 = ft.Row(controls=[sv_remaining_before_card, sv_remaining_after_card], spacing=10)

    # ---------------------------------------------------------------
    # نموذج إدخال الهدف الادخاري
    # ---------------------------------------------------------------

    goal_name_field = ft.TextField(
        label="اسم الهدف",
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    goal_amount_field = ft.TextField(
        label="المبلغ المطلوب (دينار)",
        keyboard_type=ft.KeyboardType.NUMBER,
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    goal_duration_field = ft.TextField(
        label="المدة المطلوبة (بالأشهر)",
        keyboard_type=ft.KeyboardType.NUMBER,
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    # ---------------------------------------------------------------
    # صندوق التوصية الذكية لخطة الادخار
    # ---------------------------------------------------------------

    goal_result_icon = ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=SUGGESTION_COLOR)
    goal_result_text = ft.Text(
        "أدخل تفاصيل هدفك أعلاه لعرض التحليل الذكي هنا.",
        size=13,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_600,
    )
    goal_result_detail_text = ft.Text("", size=12, color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE))

    goal_result_container = ft.Container(
        padding=14,
        border_radius=14,
        bgcolor=ft.Colors.with_opacity(0.15, SUGGESTION_COLOR),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        goal_result_icon,
                        ft.Container(content=goal_result_text, expand=True),
                    ],
                ),
                goal_result_detail_text,
            ],
        ),
    )

    def update_goal_result_ui(result: dict) -> None:
        status = result["status"]
        color = STATUS_COLOR[status]

        goal_result_container.bgcolor = ft.Colors.with_opacity(0.15, color)
        goal_result_icon.icon = STATUS_ICON[status]
        goal_result_icon.color = color
        goal_result_text.value = result["message"]

        if status == "no_income":
            goal_result_detail_text.value = ""
        else:
            goal_result_detail_text.value = (
                f"القسط الشهري المطلوب: {fmt(result['monthly_installment'])} دينار "
                f"({result['rate_percent']:.1f}% من الدخل الكلي) — "
                f"المتبقي بعد الادخار: {fmt(result['remaining_after'])} دينار"
            )
            sv_remaining_after_text.value = fmt(result["remaining_after"])

        page.update()

    # ---------------------------------------------------------------
    # قسم ربط الحساب الادخاري (IBAN / CliQ)
    # ---------------------------------------------------------------

    account_field = ft.TextField(
        label="IBAN أو معرّف CliQ",
        value=db_get_account_identifier(),
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    def handle_link_account(e: ft.Event) -> None:
        value = (account_field.value or "").strip()
        if not value:
            show_message("⚠️ الرجاء إدخال رقم الحساب (IBAN) أو معرّف CliQ.", NEGATIVE_COLOR)
            return
        db_set_account_identifier(value)
        show_message("✅ تم ربط الحساب الادخاري بنجاح.", POSITIVE_COLOR)

    link_account_button = ft.Button(
        content="🔗 ربط الحساب",
        icon=ft.Icons.LINK,
        on_click=handle_link_account,
        style=ft.ButtonStyle(
            bgcolor=SAVINGS_COLOR,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    # يحفظ آخر قسط شهري محسوب لاستخدامه في رسالة اقتراح التحويل
    last_installment_holder = {"value": 0.0}

    def handle_suggest_transfer(e: ft.Event) -> None:
        account_id = db_get_account_identifier()
        if not account_id:
            show_message("⚠️ الرجاء ربط حسابك الادخاري أولاً قبل طلب اقتراح التحويل.", NEGATIVE_COLOR)
            return
        amount = last_installment_holder["value"]
        if amount <= 0:
            show_message("⚠️ احسب هدفاً ادخارياً أولاً لعرض قيمة القسط المقترح.", NEGATIVE_COLOR)
            return
        show_message(
            f"📤 تذكير: يُقترح تحويل {fmt(amount)} دينار شهرياً يدوياً إلى الحساب "
            f"({account_id}) عبر تطبيق بنكك — هذا اقتراح فقط ولا يتم أي تحويل فعلي.",
            SAVINGS_COLOR,
        )

    suggest_transfer_button = ft.OutlinedButton(
        content="📤 اقتراح التحويل الشهري",
        icon=ft.Icons.SEND_OUTLINED,
        on_click=handle_suggest_transfer,
    )

    account_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("ربط الحساب الادخاري", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                account_field,
                ft.Row(controls=[link_account_button, suggest_transfer_button], spacing=10, wrap=True),
                ft.Text(
                    "ملاحظة: زر الاقتراح تذكير فقط لتحويل يدوي عبر تطبيق بنكك، ولا يقوم "
                    "بأي عملية تحويل فعلية للأموال.",
                    size=11,
                    color=ft.Colors.BLUE_GREY_300,
                ),
            ],
        ),
    )

    # ---------------------------------------------------------------
    # قسم الأهداف المحفوظة
    # ---------------------------------------------------------------

    savings_goals_list_column = ft.Column(spacing=8)

    def handle_delete_goal(goal_id: int) -> None:
        db_delete_savings_goal(goal_id)
        refresh_savings_ui()
        show_message("🗑 تم حذف الهدف.", ft.Colors.BLUE_GREY_400)

    def build_goal_row(
        goal_id: int,
        goal_name: str,
        target_amount: float,
        duration_months: int,
        rate: float,
        account_identifier: str,
    ) -> ft.Container:
        if rate > MAX_SAVINGS_RATE:
            tag_color = NEGATIVE_COLOR
        elif rate < MIN_SAVINGS_RATE:
            tag_color = SUGGESTION_COLOR
        else:
            tag_color = POSITIVE_COLOR

        monthly_installment = target_amount / duration_months if duration_months else 0.0

        return ft.Container(
            padding=12,
            border_radius=12,
            bgcolor=FIELD_BG,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=4,
                        expand=True,
                        controls=[
                            ft.Text(goal_name, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text(
                                f"{fmt(target_amount)} دينار خلال {duration_months} شهر "
                                f"({fmt(monthly_installment)} دينار / شهر)",
                                size=11,
                                color=ft.Colors.BLUE_GREY_300,
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=20,
                                bgcolor=ft.Colors.with_opacity(0.18, tag_color),
                                content=ft.Text(
                                    f"نسبة الادخار {rate:.1f}%",
                                    size=11,
                                    color=tag_color,
                                    weight=ft.FontWeight.W_600,
                                ),
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=NEGATIVE_COLOR,
                        tooltip="حذف",
                        on_click=lambda e, gid=goal_id: handle_delete_goal(gid),
                    ),
                ],
            ),
        )

    empty_goals_text = ft.Text(
        "لا توجد أهداف ادخارية محفوظة بعد.",
        size=13,
        color=ft.Colors.BLUE_GREY_300,
        text_align=ft.TextAlign.CENTER,
    )

    def handle_clear_all_goals_confirmed(e: ft.Event) -> None:
        db_clear_savings_goals()
        page.pop_dialog()
        refresh_savings_ui()
        show_message("🗑 تم مسح جميع الأهداف الادخارية.", ft.Colors.BLUE_GREY_400)

    def handle_clear_all_goals_cancelled(e: ft.Event) -> None:
        page.pop_dialog()

    def handle_clear_all_goals_click(e: ft.Event) -> None:
        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("تأكيد المسح"),
            content=ft.Text("هل أنت متأكد من مسح جميع الأهداف الادخارية؟ لا يمكن التراجع عن هذا الإجراء."),
            actions=[
                ft.Button(
                    content="نعم، امسح الكل",
                    on_click=handle_clear_all_goals_confirmed,
                    style=ft.ButtonStyle(bgcolor=NEGATIVE_COLOR, color=ft.Colors.WHITE),
                ),
                ft.OutlinedButton(content="إلغاء", on_click=handle_clear_all_goals_cancelled),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(confirm_dialog)

    clear_all_goals_button = ft.Button(
        content="مسح كل الأهداف",
        icon=ft.Icons.DELETE_SWEEP_OUTLINED,
        on_click=handle_clear_all_goals_click,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.with_opacity(0.15, NEGATIVE_COLOR),
            color=NEGATIVE_COLOR,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    goals_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("الأهداف المحفوظة", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                savings_goals_list_column,
                clear_all_goals_button,
            ],
        ),
    )

    # ---------------------------------------------------------------
    # زر الحساب والحفظ + منطق ربط كل شيء ببعضه
    # ---------------------------------------------------------------

    def handle_calculate_and_save_goal(e: ft.Event) -> None:
        name = (goal_name_field.value or "").strip()
        target = parse_amount(goal_amount_field.value, allow_zero=False)
        duration_months = parse_positive_int(goal_duration_field.value)

        if not name:
            show_message("⚠️ الرجاء إدخال اسم الهدف.", NEGATIVE_COLOR)
            return
        if target is None:
            show_message("⚠️ الرجاء إدخال مبلغ هدف صحيح وموجب.", NEGATIVE_COLOR)
            return
        if duration_months is None:
            show_message("⚠️ الرجاء إدخال مدة صحيحة بالأشهر (عدد صحيح موجب).", NEGATIVE_COLOR)
            return

        income = db_get_income()
        total_expenses = db_get_total_expenses()
        remaining_before = income - total_expenses

        result = analyze_savings_goal(income, remaining_before, target, duration_months)

        if result["status"] == "no_income":
            update_goal_result_ui(result)
            show_message("⚠️ سجّل دخلك الشهري من الشاشة الرئيسية أولاً.", NEGATIVE_COLOR)
            return

        account_id = db_get_account_identifier()
        db_add_savings_goal(name, target, duration_months, result["rate_percent"], account_id)

        goal_name_field.value = ""
        goal_amount_field.value = ""
        goal_duration_field.value = ""

        last_installment_holder["value"] = result["monthly_installment"]

        refresh_savings_ui()
        update_goal_result_ui(result)

        if result["status"] == "over":
            show_message("⚠️ تم حفظ الهدف، لكنه يحتاج مراجعة — راجع التوصية أعلاه.", NEGATIVE_COLOR)
        else:
            show_message("✅ تم حساب الهدف وحفظه بنجاح.", POSITIVE_COLOR)

    calculate_goal_button = ft.Button(
        content="🧮 احسب واحفظ الهدف",
        icon=ft.Icons.CALCULATE_OUTLINED,
        on_click=handle_calculate_and_save_goal,
        style=ft.ButtonStyle(
            bgcolor=SAVINGS_COLOR,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    goal_form_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("حدد هدفك الادخاري", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                goal_name_field,
                goal_amount_field,
                goal_duration_field,
                calculate_goal_button,
            ],
        ),
    )

    # ---------------------------------------------------------------
    # منطق تحديث واجهة صفحة الادخار بالكامل
    # ---------------------------------------------------------------

    def refresh_savings_ui() -> None:
        income = db_get_income()
        total_expenses = db_get_total_expenses()
        remaining_before = income - total_expenses

        sv_income_text.value = fmt(income)
        sv_expenses_text.value = fmt(total_expenses)
        sv_remaining_before_text.value = fmt(remaining_before)
        sv_remaining_after_text.value = fmt(remaining_before)

        account_field.value = db_get_account_identifier()

        goals = db_get_savings_goals()
        savings_goals_list_column.controls.clear()
        if goals:
            for goal_id, goal_name, target_amount, duration_months, rate, account_identifier in goals:
                savings_goals_list_column.controls.append(
                    build_goal_row(goal_id, goal_name, target_amount, duration_months, rate, account_identifier)
                )
        else:
            savings_goals_list_column.controls.append(empty_goals_text)

        page.update()

    # ---------------------------------------------------------------
    # تركيب واجهة صفحة الادخار
    # ---------------------------------------------------------------

    savings_header = ft.Container(
        padding=ft.Padding.only(top=20, bottom=10, left=20, right=20),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    icon_color=ft.Colors.WHITE,
                    tooltip="العودة للشاشة الرئيسية",
                    on_click=lambda e: show_home_view(),
                ),
                ft.Icon(ft.Icons.SAVINGS_OUTLINED, color=SAVINGS_COLOR, size=24),
                ft.Text(
                    "الحساب الادخاري والتخطيط الذكي",
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
            ],
        ),
    )

    savings_body = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=16,
        controls=[
            savings_header,
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=20),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        sv_summary_row_1,
                        sv_summary_row_2,
                        goal_form_section,
                        goal_result_container,
                        account_section,
                        goals_section,
                        ft.Container(height=20),
                    ],
                ),
            ),
        ],
    )

    # =================================================================
    # ===================== التنقل بين الشاشتين =========================
    # =================================================================

    view_container = ft.Container(expand=True, content=home_body)

    def show_home_view() -> None:
        view_container.content = home_body
        refresh_ui()

    def show_savings_view() -> None:
        view_container.content = savings_body
        refresh_savings_ui()

    page.add(ft.SafeArea(expand=True, content=view_container))

    refresh_ui()


ft.run(main)
