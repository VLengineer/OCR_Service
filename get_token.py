import time
import jwt

SECRET = "DqjYCpgrf9pMJER9mNzC0st3kWPQ2f2Cei8q2IUq5u60MvCGwnkD-fQ7wEF36JCB"

payload = {
    "sub": "external-service",
    "iss": "my-app",
    "iat": int(time.time()),
    # можно добавить любые свои claims: roles, tenant_id и т.д.
}

token = jwt.encode(payload, SECRET, algorithm="HS256")
print(token)
#eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJleHRlcm5hbC1zZXJ2aWNlIiwiaXNzIjoibXktYXBwIiwiaWF0IjoxNzkyMDUzMjg0LCJleHAiOjE3OTIwNTY4ODR9.svn2AbCfLyQ5mJaUlWhhLs8nJ5n8wXdWNJ1xke3VTRE