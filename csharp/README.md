# Set Up C# in VS Code

1. Install VS Code and complete steps on "Welcome" page.
2. Install `@id:ms-dotnettools.csdevkit` (C# Dev Kit) in VS Code
3. Install .net `https://dotnet.microsoft.com/en-us/download`
4. Go to terminal and run `dotnet --version` and check if it exists. (If not, scroll down)
5. Go to terminal in VS Code and run `dotnet build` to create and add a file to .csproj (.csproj is created with 1st .cs file in folder)
6. Use `dotnet run` to run the .csproj.

Note: dotnet run will compile and run all files inside .csproj

# If this happens:
`dotnet --version`
`zsh: command not found: dotnet`

1. Check if it is actually installed: `ls /usr/local/share/dotnet`. If `No such file or directory`, dotnet is not installed; use `brew install --cask dotnet`.
2. If installed, run `sudo ln -s /usr/local/share/dotnet/dotnet /usr/local/bin/dotnet`
3. If it doesn't work, it probably means /usr/local/bin does not exist. Run `sudo mkdir -p /usr/local/bin` then try again.
