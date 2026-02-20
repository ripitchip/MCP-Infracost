from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
import subprocess
import os
import tempfile
from pathlib import Path

router = APIRouter()


class TerraformCode(BaseModel):
    content: str
    filename: str = "main.tf"


class LintResult(BaseModel):
    valid: bool
    message: str
    errors: list = []
    warnings: list = []


@router.post("/tflint/validate")
async def validate_terraform(terraform: TerraformCode) -> LintResult:
    """
    Valide et analyse la syntaxe d'un fichier Terraform.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Écrire le contenu terraform dans un fichier temporaire
            tf_file = Path(tmpdir) / terraform.filename
            tf_file.write_text(terraform.content)
            
            # Vérifier si tflint est disponible, sinon utiliser terraform validate
            try:
                result = subprocess.run(
                    ["tflint", str(tmpdir)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return LintResult(
                        valid=True,
                        message="Terraform code is valid",
                        errors=[]
                    )
                else:
                    return LintResult(
                        valid=False,
                        message="Terraform linting failed",
                        errors=result.stdout.split('\n') if result.stdout else [],
                        warnings=result.stderr.split('\n') if result.stderr else []
                    )
            except FileNotFoundError:
                # Fallback sur terraform validate
                result = subprocess.run(
                    ["terraform", "validate", "-json"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return LintResult(
                        valid=True,
                        message="Terraform code is valid",
                        errors=[]
                    )
                else:
                    return LintResult(
                        valid=False,
                        message="Terraform validation failed",
                        errors=[result.stderr] if result.stderr else []
                    )
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Validation timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/tflint/check-syntax")
async def check_terraform_syntax(terraform: TerraformCode) -> dict:
    """
    Vérifie la syntaxe basique d'un fichier Terraform.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tf_file = Path(tmpdir) / terraform.filename
            tf_file.write_text(terraform.content)
            
            result = subprocess.run(
                ["terraform", "fmt", "-check", str(tf_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return {
                "formatted": result.returncode == 0,
                "message": "Code is properly formatted" if result.returncode == 0 else "Code needs formatting",
                "output": result.stdout if result.stdout else result.stderr
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/tflint/status")
async def tflint_status() -> dict:
    """
    Vérifie la disponibilité des outils Terraform.
    """
    tools_status = {}
    
    # Chercher terraform
    result = subprocess.run(["which", "terraform"], capture_output=True)
    tools_status["terraform"] = result.returncode == 0
    
    # Chercher tflint
    result = subprocess.run(["which", "tflint"], capture_output=True)
    tools_status["tflint"] = result.returncode == 0
    
    return {
        "available_tools": tools_status,
        "primary_tool": "tflint" if tools_status.get("tflint") else "terraform"
    }
