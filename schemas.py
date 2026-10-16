from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class IncomeBase(BaseModel):
    transaction_date: date
    income_type: str
    payment_method: str
    amount: float
    description: Optional[str] = None

class IncomeCreate(IncomeBase):
    pass

class Income(IncomeBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ExpenseCategoryBase(BaseModel):
    name: str

class ExpenseCategoryCreate(ExpenseCategoryBase):
    pass

class ExpenseCategory(ExpenseCategoryBase):
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ExpenseBase(BaseModel):
    transaction_date: date
    category_id: int
    amount: float
    description: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    pass

class Expense(ExpenseBase):
    id: int
    category: ExpenseCategory
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmployeeBase(BaseModel):
    name: str
    role: str
    monthly_salary: float

class EmployeeCreate(EmployeeBase):
    pass

class Employee(EmployeeBase):
    id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RecurringExpenseBase(BaseModel):
    name: str
    category_id: int
    amount: float
    frequency: str = "Monthly"
    due_day: int

class RecurringExpenseCreate(RecurringExpenseBase):
    pass

class RecurringExpense(RecurringExpenseBase):
    id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class Token(BaseModel):
    token: str
