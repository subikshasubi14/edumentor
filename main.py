from fastapi import FastAPI, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import date, datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
import jwt
from passlib.context import CryptContext

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import models, schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Institute Finance Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "supersecretkey_please_change"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Helper function to seed initial categories
def seed_categories(db: Session):
    default_categories = [
        "Rent", "EB Bill", "WiFi", "HR Phone Recharge", "Justdial",
        "Digital Marketing / Ads", "Staff Salary", "Travel Expense",
        "Maintenance", "Other"
    ]
    if db.query(models.ExpenseCategory).count() == 0:
        for cat in default_categories:
            db.add(models.ExpenseCategory(name=cat))
        db.commit()

def seed_admin(db: Session):
    if db.query(models.User).count() == 0:
        hashed_pw = get_password_hash("admin123")
        db.add(models.User(username="admin", password_hash=hashed_pw))
        db.commit()

@app.on_event("startup")
def startup_event():
    db = next(get_db())
    seed_categories(db)
    seed_admin(db)

@app.post("/api/login", response_model=schemas.Token)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token = create_access_token(data={"sub": db_user.username})
    return {"token": access_token}

@app.post("/api/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pw = get_password_hash(user.password)
    new_user = models.User(username=user.username, password_hash=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.username})
    return {"token": access_token}

@app.get("/api/dashboard/summary")
def get_dashboard_summary(month: int, year: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    income_query = db.query(func.sum(models.IncomeTransaction.amount)).filter(
        extract('month', models.IncomeTransaction.transaction_date) == month,
        extract('year', models.IncomeTransaction.transaction_date) == year
    ).scalar() or 0.0

    expense_query = db.query(func.sum(models.ExpenseTransaction.amount)).filter(
        extract('month', models.ExpenseTransaction.transaction_date) == month,
        extract('year', models.ExpenseTransaction.transaction_date) == year
    ).scalar() or 0.0

    profit = income_query - expense_query if income_query > expense_query else 0
    loss = expense_query - income_query if expense_query > income_query else 0

    return {
        "total_income": income_query,
        "total_expense": expense_query,
        "profit": profit,
        "loss": loss
    }

@app.get("/api/income", response_model=List[schemas.Income])
def get_incomes(month: int = None, year: int = None, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    query = db.query(models.IncomeTransaction)
    if month and year:
        query = query.filter(
            extract('month', models.IncomeTransaction.transaction_date) == month,
            extract('year', models.IncomeTransaction.transaction_date) == year
        )
    return query.order_by(models.IncomeTransaction.transaction_date.desc()).all()

@app.post("/api/income", response_model=schemas.Income)
def create_income(income: schemas.IncomeCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_income = models.IncomeTransaction(**income.model_dump())
    db.add(db_income)
    db.commit()
    db.refresh(db_income)
    return db_income


@app.get("/api/expenses", response_model=List[schemas.Expense])
def get_expenses(month: int = None, year: int = None, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    query = db.query(models.ExpenseTransaction)
    if month and year:
        query = query.filter(
            extract('month', models.ExpenseTransaction.transaction_date) == month,
            extract('year', models.ExpenseTransaction.transaction_date) == year
        )
    return query.order_by(models.ExpenseTransaction.transaction_date.desc()).all()

@app.post("/api/expenses", response_model=schemas.Expense)
def create_expense(expense: schemas.ExpenseCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_expense = models.ExpenseTransaction(**expense.model_dump())
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/api/categories", response_model=List[schemas.ExpenseCategory])
def get_categories(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return db.query(models.ExpenseCategory).all()

from pydantic import BaseModel
class StatusUpdate(BaseModel):
    status: str

@app.post("/api/categories", response_model=schemas.ExpenseCategory)
def create_category(category: schemas.ExpenseCategoryCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_category = models.ExpenseCategory(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.put("/api/categories/{id}/status", response_model=schemas.ExpenseCategory)
def update_category_status(id: int, status_update: StatusUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_category = db.query(models.ExpenseCategory).filter(models.ExpenseCategory.id == id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    db_category.status = status_update.status
    db.commit()
    db.refresh(db_category)
    return db_category

@app.delete("/api/categories/{id}")
def delete_category(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_category = db.query(models.ExpenseCategory).filter(models.ExpenseCategory.id == id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(db_category)
    db.commit()
    return {"message": "Deleted successfully"}

@app.delete("/api/income/{id}")
def delete_income(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_income = db.query(models.IncomeTransaction).filter(models.IncomeTransaction.id == id).first()
    if not db_income:
        raise HTTPException(status_code=404, detail="Income not found")
    db.delete(db_income)
    db.commit()
    return {"message": "Deleted successfully"}

@app.delete("/api/expenses/{id}")
def delete_expense(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_expense = db.query(models.ExpenseTransaction).filter(models.ExpenseTransaction.id == id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(db_expense)
    db.commit()
    return {"message": "Deleted successfully"}

@app.get("/api/recurring-expenses", response_model=List[schemas.RecurringExpense])
def get_recurring_expenses(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return db.query(models.RecurringExpense).all()

@app.post("/api/recurring-expenses", response_model=schemas.RecurringExpense)
def create_recurring_expense(rec: schemas.RecurringExpenseCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_rec = models.RecurringExpense(**rec.model_dump())
    db.add(db_rec)
    db.commit()
    db.refresh(db_rec)
    return db_rec

@app.put("/api/recurring-expenses/{id}", response_model=schemas.RecurringExpense)
def update_recurring_expense(id: int, rec_update: schemas.RecurringExpenseCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_rec = db.query(models.RecurringExpense).filter(models.RecurringExpense.id == id).first()
    if not db_rec:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    for key, value in rec_update.model_dump().items():
        setattr(db_rec, key, value)
    db.commit()
    db.refresh(db_rec)
    return db_rec

@app.delete("/api/recurring-expenses/{id}")
def delete_recurring_expense(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_rec = db.query(models.RecurringExpense).filter(models.RecurringExpense.id == id).first()
    if not db_rec:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    db.delete(db_rec)
    db.commit()
    return {"message": "Deleted successfully"}

@app.get("/api/employees", response_model=List[schemas.Employee])
def get_employees(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return db.query(models.Employee).all()

@app.post("/api/employees", response_model=schemas.Employee)
def create_employee(emp: schemas.EmployeeCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_emp = models.Employee(**emp.model_dump())
    db.add(db_emp)
    db.commit()
    db.refresh(db_emp)
    return db_emp

@app.put("/api/employees/{id}", response_model=schemas.Employee)
def update_employee(id: int, emp_update: schemas.EmployeeCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_emp = db.query(models.Employee).filter(models.Employee.id == id).first()
    if not db_emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    for key, value in emp_update.model_dump().items():
        setattr(db_emp, key, value)
    db.commit()
    db.refresh(db_emp)
    return db_emp

@app.delete("/api/employees/{id}")
def delete_employee(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_emp = db.query(models.Employee).filter(models.Employee.id == id).first()
    if not db_emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(db_emp)
    db.commit()
    return {"message": "Deleted successfully"}
