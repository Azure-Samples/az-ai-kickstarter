### Dependency Installation 

#### Deployment pre-requisites

Codespaces and DevContainer come with all deployment and development pre-requisites already installed.

##### Windows PowerShell

On Windows you can install the pre-requisites by executing the following commands in a PowerShell terminal:
```powershell
winget install Python.Python.3.12
winget install Microsoft.PowerShell
winget install Microsoft.AzureCLI
winget install Microsoft.Azd
winget install Microsoft.Git
```

Install `uv` following the installation instructions [here](https://docs.astral.sh/uv/getting-started/installation/):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

##### Ubuntu/WSL

Install `uv` following the installation instructions [here](https://docs.astral.sh/uv/getting-started/installation/):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

##### MacOSX:

On MacOS you can install the dependencies with [HomeBrew](https://brew.sh/):
```bash
brew install python
brew install azure-cli
brew tap azure/azure-dev # Add the Azure Dev tap if not already added
brew install azure-dev
brew install git
```

Install `uv` following the installation instructions [here](https://docs.astral.sh/uv/getting-started/installation/):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
