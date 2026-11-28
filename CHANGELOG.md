# Changelog

## [0.1.0-rc.3](https://github.com/Promethean-Works/athena/compare/v0.1.0-rc.2...v0.1.0-rc.3) (2026-11-28)


### Features

* **auth:** add multi-user support with admin and user roles ([#324](https://github.com/Promethean-Works/athena/issues/324)) ([c4cf92f](https://github.com/Promethean-Works/athena/commit/c4cf92ff90e019e83b4633f7db140ac7d3893487))
* **catalog:** add 23 apps, mostly AI ([#310](https://github.com/Promethean-Works/athena/issues/310)) ([ce318e4](https://github.com/Promethean-Works/athena/commit/ce318e466065d7ba346c85d7e557b89059072915))
* **catalog:** app files, optional parts (profiles) and Docker-access flag ([#314](https://github.com/Promethean-Works/athena/issues/314)) ([d6ce8ed](https://github.com/Promethean-Works/athena/commit/d6ce8ed33e05773e1482bbb2ab0a61b11cb5591f))
* **dashboard:** list folders, cloud remotes and network shares on the storage card ([#301](https://github.com/Promethean-Works/athena/issues/301)) ([3958201](https://github.com/Promethean-Works/athena/commit/3958201bb4ac1277b17971fef25a5203d7d0e582))
* **files:** per-user folders and per-location access for plain users ([#341](https://github.com/Promethean-Works/athena/issues/341)) ([b647d75](https://github.com/Promethean-Works/athena/commit/b647d75452bcb0047d268ded0bf670996c90e0d3))
* **onboarding:** setup wizard on the web and in the CLI, with runtime install ([#325](https://github.com/Promethean-Works/athena/issues/325)) ([7f1c719](https://github.com/Promethean-Works/athena/commit/7f1c7199119577872b3f4bc7ae3367244a6e07f7))
* **packages:** full package manager UI (search, details, icons, add a manager) ([#327](https://github.com/Promethean-Works/athena/issues/327)) ([270ea66](https://github.com/Promethean-Works/athena/commit/270ea66534def0e40ddebd11a9f0ff34bb71ea13))
* **shares:** add a Network shares page with SMB and NFS tabs ([#312](https://github.com/Promethean-Works/athena/issues/312)) ([647a225](https://github.com/Promethean-Works/athena/commit/647a225ae61982527329b440b9a7d83a04604f52))
* **shares:** check the host password before the action runs ([#332](https://github.com/Promethean-Works/athena/issues/332)) ([4c4bbbe](https://github.com/Promethean-Works/athena/commit/4c4bbbe5beff83fe50fcafccc4f91b202031232f))
* **shares:** export locations over NFS and roll back failed share reloads ([#304](https://github.com/Promethean-Works/athena/issues/304)) ([7aaf39c](https://github.com/Promethean-Works/athena/commit/7aaf39c55c4abde291b2e900c176b76ab54760ca))
* **shares:** share a sub-folder of a location over SMB or NFS ([#323](https://github.com/Promethean-Works/athena/issues/323)) ([39bb978](https://github.com/Promethean-Works/athena/commit/39bb978d6095a85544cb01bb1d3a9d24fd010ee1))
* **shares:** share folders over SMB and NFS on macOS ([#307](https://github.com/Promethean-Works/athena/issues/307)) ([a44c88a](https://github.com/Promethean-Works/athena/commit/a44c88ada6186993b3986ba6b1dd16581703956e))
* **shares:** share folders over SMB on Windows ([#309](https://github.com/Promethean-Works/athena/issues/309)) ([10855a0](https://github.com/Promethean-Works/athena/commit/10855a0aae85afdec3e90d90ad9012243f2519bb))
* **shares:** share from the file explorer and ask for the password ([#317](https://github.com/Promethean-Works/athena/issues/317)) ([c8afd3d](https://github.com/Promethean-Works/athena/commit/c8afd3d6f80def80e7fd1de648b330a4df19a1cc))
* **site:** star on GitHub button with live star count ([#342](https://github.com/Promethean-Works/athena/issues/342)) ([52340d9](https://github.com/Promethean-Works/athena/commit/52340d92582dd03f71b4cd6c9284626db5fb4134))
* **web:** add i18n with 22 languages ([#313](https://github.com/Promethean-Works/athena/issues/313)) ([acea80d](https://github.com/Promethean-Works/athena/commit/acea80d214d41adeb3efd551a7176c83e59611de))
* **web:** add the Athena logo to the dashboard and website ([#318](https://github.com/Promethean-Works/athena/issues/318)) ([3a79de9](https://github.com/Promethean-Works/athena/commit/3a79de9564b286067b601f105dee311e8ae9a01a))
* **web:** redraw the logo as a temple ([#319](https://github.com/Promethean-Works/athena/issues/319)) ([318a913](https://github.com/Promethean-Works/athena/commit/318a913675b9649fcafc988c8ef97cc4457405b1))


### Bug Fixes

* **files:** close Athena's data folder and app definitions to plain users ([#340](https://github.com/Promethean-Works/athena/issues/340)) ([9dc6f98](https://github.com/Promethean-Works/athena/commit/9dc6f98554cd1cefd0566777ad806d9f05bd0abd))
* **packages:** no border on icons, descriptions in search, cap the version column ([#328](https://github.com/Promethean-Works/athena/issues/328)) ([6cfea2e](https://github.com/Promethean-Works/athena/commit/6cfea2ee1cf6f25821aa91650d5940773f6c390f))
* **security:** audit fixes for auth, shares, jobs, downloads and the assistant ([#339](https://github.com/Promethean-Works/athena/issues/339)) ([d081c6b](https://github.com/Promethean-Works/athena/commit/d081c6b79e30dce708954871e46701f099a0c841))
* **shares:** ask for the host password on the Network shares page ([#329](https://github.com/Promethean-Works/athena/issues/329)) ([5d780a5](https://github.com/Promethean-Works/athena/commit/5d780a57b84e4c8057bd36ba5f779903b98a6ff4))
* **shares:** ask for the host password when removing a share ([#330](https://github.com/Promethean-Works/athena/issues/330)) ([eb863f5](https://github.com/Promethean-Works/athena/commit/eb863f50c7a92c57c6b742d41f16755b67993d5f))

## [0.1.0-rc.2](https://github.com/Promethean-Works/athena/compare/v0.1.0-rc.1...v0.1.0-rc.2) (2026-11-26)


### Features

* **tunnel:** show a QR code for the tunnel address ([#293](https://github.com/Promethean-Works/athena/issues/293)) ([6df6174](https://github.com/Promethean-Works/athena/commit/6df6174b7834129274efe76329ff4eed15108afa))


### Bug Fixes

* **ci:** bump release-please prereleases (rc.1 to rc.2) instead of the patch ([#300](https://github.com/Promethean-Works/athena/issues/300)) ([e05ec5c](https://github.com/Promethean-Works/athena/commit/e05ec5ca3b158f38c900f1dc8a2a288cf60971db))
* **ci:** drop release-as so release-please stops re-proposing rc.1 ([#297](https://github.com/Promethean-Works/athena/issues/297)) ([a4fbcef](https://github.com/Promethean-Works/athena/commit/a4fbcefedb52e357bed5c903ba65c45c4d6e483e))
* **cloud:** show next unit when size rounds to 1000 ([#290](https://github.com/Promethean-Works/athena/issues/290)) ([a91fe1d](https://github.com/Promethean-Works/athena/commit/a91fe1d22046f9641d04b851163671dea4f95f99))
* **dashboard:** make app tile icons 1.5x bigger ([#299](https://github.com/Promethean-Works/athena/issues/299)) ([b6efab3](https://github.com/Promethean-Works/athena/commit/b6efab338b8a2c86f1613a1cbb22cfc852da9195))
* **dashboard:** show apps as icon tiles and fix card bottom padding ([#298](https://github.com/Promethean-Works/athena/issues/298)) ([089c642](https://github.com/Promethean-Works/athena/commit/089c6424b8c7256c6900ddc6e5f111ad9890f940))
* **e2e:** rewrite the wheel's Version header whatever its spelling ([#291](https://github.com/Promethean-Works/athena/issues/291)) ([763ad06](https://github.com/Promethean-Works/athena/commit/763ad065fc256789c5119efd18b192b275e120be))
* **setup:** set CSRF token after account creation ([#287](https://github.com/Promethean-Works/athena/issues/287)) ([901dc41](https://github.com/Promethean-Works/athena/commit/901dc41b47f4f47ba13c661a0168dcb6f0a63b4e))
* **tunnel:** detect cloudflared and ngrok installed outside PATH ([#289](https://github.com/Promethean-Works/athena/issues/289)) ([af8fd1c](https://github.com/Promethean-Works/athena/commit/af8fd1c15b43331df6ac2441369d7ffe761edfa7))

## [0.1.0-rc.1](https://github.com/Promethean-Works/athena/compare/v0.1.0-rc.1...v0.1.0-rc.1) (2026-11-26)


### Features

* **tunnel:** show a QR code for the tunnel address ([#293](https://github.com/Promethean-Works/athena/issues/293)) ([6df6174](https://github.com/Promethean-Works/athena/commit/6df6174b7834129274efe76329ff4eed15108afa))


### Bug Fixes

* **cloud:** show next unit when size rounds to 1000 ([#290](https://github.com/Promethean-Works/athena/issues/290)) ([a91fe1d](https://github.com/Promethean-Works/athena/commit/a91fe1d22046f9641d04b851163671dea4f95f99))
* **e2e:** rewrite the wheel's Version header whatever its spelling ([#291](https://github.com/Promethean-Works/athena/issues/291)) ([763ad06](https://github.com/Promethean-Works/athena/commit/763ad065fc256789c5119efd18b192b275e120be))
* **setup:** set CSRF token after account creation ([#287](https://github.com/Promethean-Works/athena/issues/287)) ([901dc41](https://github.com/Promethean-Works/athena/commit/901dc41b47f4f47ba13c661a0168dcb6f0a63b4e))
* **tunnel:** detect cloudflared and ngrok installed outside PATH ([#289](https://github.com/Promethean-Works/athena/issues/289)) ([af8fd1c](https://github.com/Promethean-Works/athena/commit/af8fd1c15b43331df6ac2441369d7ffe761edfa7))

## [0.1.0-rc.1](https://github.com/Promethean-Works/athena/compare/v0.1.0-rc.1...v0.1.0-rc.1) (2026-11-26)


### Features

* **tunnel:** show a QR code for the tunnel address ([#293](https://github.com/Promethean-Works/athena/issues/293)) ([6df6174](https://github.com/Promethean-Works/athena/commit/6df6174b7834129274efe76329ff4eed15108afa))


### Bug Fixes

* **cloud:** show next unit when size rounds to 1000 ([#290](https://github.com/Promethean-Works/athena/issues/290)) ([a91fe1d](https://github.com/Promethean-Works/athena/commit/a91fe1d22046f9641d04b851163671dea4f95f99))
* **e2e:** rewrite the wheel's Version header whatever its spelling ([#291](https://github.com/Promethean-Works/athena/issues/291)) ([763ad06](https://github.com/Promethean-Works/athena/commit/763ad065fc256789c5119efd18b192b275e120be))
* **setup:** set CSRF token after account creation ([#287](https://github.com/Promethean-Works/athena/issues/287)) ([901dc41](https://github.com/Promethean-Works/athena/commit/901dc41b47f4f47ba13c661a0168dcb6f0a63b4e))
* **tunnel:** detect cloudflared and ngrok installed outside PATH ([#289](https://github.com/Promethean-Works/athena/issues/289)) ([af8fd1c](https://github.com/Promethean-Works/athena/commit/af8fd1c15b43331df6ac2441369d7ffe761edfa7))

## [0.1.0-rc.1](https://github.com/Promethean-Works/athena/compare/v0.1.0-rc.1...v0.1.0-rc.1) (2026-11-26)


### Features

* **tunnel:** show a QR code for the tunnel address ([#293](https://github.com/Promethean-Works/athena/issues/293)) ([6df6174](https://github.com/Promethean-Works/athena/commit/6df6174b7834129274efe76329ff4eed15108afa))


### Bug Fixes

* **cloud:** show next unit when size rounds to 1000 ([#290](https://github.com/Promethean-Works/athena/issues/290)) ([a91fe1d](https://github.com/Promethean-Works/athena/commit/a91fe1d22046f9641d04b851163671dea4f95f99))
* **e2e:** rewrite the wheel's Version header whatever its spelling ([#291](https://github.com/Promethean-Works/athena/issues/291)) ([763ad06](https://github.com/Promethean-Works/athena/commit/763ad065fc256789c5119efd18b192b275e120be))
* **setup:** set CSRF token after account creation ([#287](https://github.com/Promethean-Works/athena/issues/287)) ([901dc41](https://github.com/Promethean-Works/athena/commit/901dc41b47f4f47ba13c661a0168dcb6f0a63b4e))
* **tunnel:** detect cloudflared and ngrok installed outside PATH ([#289](https://github.com/Promethean-Works/athena/issues/289)) ([af8fd1c](https://github.com/Promethean-Works/athena/commit/af8fd1c15b43331df6ac2441369d7ffe761edfa7))

## [0.1.0-rc.1](https://github.com/Promethean-Works/athena/compare/v0.1.0-rc.1...v0.1.0-rc.1) (2026-11-26)


### Bug Fixes

* **cloud:** show next unit when size rounds to 1000 ([#290](https://github.com/Promethean-Works/athena/issues/290)) ([a91fe1d](https://github.com/Promethean-Works/athena/commit/a91fe1d22046f9641d04b851163671dea4f95f99))
* **e2e:** rewrite the wheel's Version header whatever its spelling ([#291](https://github.com/Promethean-Works/athena/issues/291)) ([763ad06](https://github.com/Promethean-Works/athena/commit/763ad065fc256789c5119efd18b192b275e120be))
* **setup:** set CSRF token after account creation ([#287](https://github.com/Promethean-Works/athena/issues/287)) ([901dc41](https://github.com/Promethean-Works/athena/commit/901dc41b47f4f47ba13c661a0168dcb6f0a63b4e))
* **tunnel:** detect cloudflared and ngrok installed outside PATH ([#289](https://github.com/Promethean-Works/athena/issues/289)) ([af8fd1c](https://github.com/Promethean-Works/athena/commit/af8fd1c15b43331df6ac2441369d7ffe761edfa7))

## 0.1.0-rc.1 (2026-11-25)


### Features

* **agents:** add athena-orchestrate skill and orchestrate.mjs ([#272](https://github.com/Promethean-Works/athena/issues/272)) ([d3450f0](https://github.com/Promethean-Works/athena/commit/d3450f0aaccd775782fbeb660899401bef494dfc))
* **agents:** give oh-my-pi STATUS and secret-file blocking ([#189](https://github.com/Promethean-Works/athena/issues/189)) ([539c6c4](https://github.com/Promethean-Works/athena/commit/539c6c4474d3b2bf4636c1e63304db1bff5ad2b0))
* **agents:** native guards, worktrees, subagents and commands for each agent ([#263](https://github.com/Promethean-Works/athena/issues/263)) ([78bec19](https://github.com/Promethean-Works/athena/commit/78bec191fba67b8853d222e27c8ede1fbe87be33))
* **agents:** orchestrate pr and ci steps ([#279](https://github.com/Promethean-Works/athena/issues/279)) ([ce230d9](https://github.com/Promethean-Works/athena/commit/ce230d915916e62be85415be8c26b288d33870db))
* **agents:** shared workflow commands, reviewer subagent and secret guards ([#155](https://github.com/Promethean-Works/athena/issues/155)) ([a93f7b2](https://github.com/Promethean-Works/athena/commit/a93f7b2018c6ee145d41f54559e5fb01b770bc5f))
* **agents:** support oh-my-pi ([#185](https://github.com/Promethean-Works/athena/issues/185)) ([c26a487](https://github.com/Promethean-Works/athena/commit/c26a4874a8be64d4a68b64d9743425d1bfa64186))
* app store with a built-in catalog of 20 apps (M3 part A) ([#17](https://github.com/Promethean-Works/athena/issues/17)) ([9f526a7](https://github.com/Promethean-Works/athena/commit/9f526a7b76825d1e2f36794c72d63c94c49dabd6))
* apps from compose files and docker run commands (M2 part B) ([#16](https://github.com/Promethean-Works/athena/issues/16)) ([447980e](https://github.com/Promethean-Works/athena/commit/447980eed1fe5f6ccaf2f1f5832ac0bc1dba45b9))
* **apps:** rename Form tab to Settings and enable two-way YAML sync ([#141](https://github.com/Promethean-Works/athena/issues/141)) ([b1faf56](https://github.com/Promethean-Works/athena/commit/b1faf569bcaee6c2b5d4e9a04b1cf456da78b880))
* **assistant:** add a plan per chat and multiple-choice questions ([#66](https://github.com/Promethean-Works/athena/issues/66)) ([d1b7bb7](https://github.com/Promethean-Works/athena/commit/d1b7bb78c42a519c6831a5446f7d9fa67c192ad5))
* **assistant:** add actions with approval cards ([#39](https://github.com/Promethean-Works/athena/issues/39)) ([e0f4fee](https://github.com/Promethean-Works/athena/commit/e0f4feeb4217bf800e2fc83f7236b98576e06046))
* **assistant:** add AI providers, Settings → AI and streaming chat ([#37](https://github.com/Promethean-Works/athena/issues/37)) ([46db2d5](https://github.com/Promethean-Works/athena/commit/46db2d5bdb012ccfc678ba06ed6c3bb767263a55))
* **assistant:** add an optional advisor model the assistant can consult ([#68](https://github.com/Promethean-Works/athena/issues/68)) ([7c733a2](https://github.com/Promethean-Works/athena/commit/7c733a21dab3171ebea4bca648089c36a2a640d2))
* **assistant:** add browser capability, blocked on harness release ([#89](https://github.com/Promethean-Works/athena/issues/89)) ([2b9007a](https://github.com/Promethean-Works/athena/commit/2b9007a7417f27e0d20c9c4fa230ad3b2bd69f94))
* **assistant:** add Code Mode and durable execution Postgres verification ([#88](https://github.com/Promethean-Works/athena/issues/88)) ([6f014b0](https://github.com/Promethean-Works/athena/commit/6f014b08cbbee350840e211aeaed1813030a9de1))
* **assistant:** add Coder to the coding stack ([#85](https://github.com/Promethean-Works/athena/issues/85)) ([4656c86](https://github.com/Promethean-Works/athena/commit/4656c869bf11aab3e5bd3a3e48e213e2dc29abed))
* **assistant:** add coding stack setting and RepoContext capability (M7 D.7) ([#81](https://github.com/Promethean-Works/athena/issues/81)) ([8d19ef8](https://github.com/Promethean-Works/athena/commit/8d19ef8acddab24ced098afae2ca8f1046d57347))
* **assistant:** add Docker sandbox (M7 D stage 3) ([#77](https://github.com/Promethean-Works/athena/issues/77)) ([66944da](https://github.com/Promethean-Works/athena/commit/66944daa8a8fa0ff46c58cdd49c8f558faccb51d))
* **assistant:** add durable execution setting and pgtask capability (M7 D.6 foundation) ([#80](https://github.com/Promethean-Works/athena/issues/80)) ([79610a2](https://github.com/Promethean-Works/athena/commit/79610a234f356d0673e8e88f3b413c1ddfc1fd84))
* **assistant:** add Exa web research (M7 D stage 3) ([#75](https://github.com/Promethean-Works/athena/issues/75)) ([9e7a821](https://github.com/Promethean-Works/athena/commit/9e7a8213a39ce00dac02b73e72b31e64d22eedc4))
* **assistant:** add filesystem write/edit capabilities to coding stack ([#84](https://github.com/Promethean-Works/athena/issues/84)) ([f0d2246](https://github.com/Promethean-Works/athena/commit/f0d2246eab9f6b480a4e3fa2ba08091c43327fdc))
* **assistant:** add hosted integrations (M7 part D.5) ([#78](https://github.com/Promethean-Works/athena/issues/78)) ([b610d68](https://github.com/Promethean-Works/athena/commit/b610d688584f825f01776d5c014773d3f5b8dc04))
* **assistant:** add memory across chats and skills with an artifact scanner ([#65](https://github.com/Promethean-Works/athena/issues/65)) ([0244108](https://github.com/Promethean-Works/athena/commit/0244108e17aac5cb298095d650ba60751efc81b1))
* **assistant:** add pydantic mcp client toolsets for all agents ([#70](https://github.com/Promethean-Works/athena/issues/70)) ([6761a87](https://github.com/Promethean-Works/athena/commit/6761a871f5ea8ae49a308709612cacd922f69a37))
* **assistant:** add second-model review of action approvals (M7 D stage 3) ([#76](https://github.com/Promethean-Works/athena/issues/76)) ([ed2c9e2](https://github.com/Promethean-Works/athena/commit/ed2c9e276153c1465dbc1040a138da20a43656c0))
* **assistant:** add stay-on-task reminders and log prompt cache busts ([#64](https://github.com/Promethean-Works/athena/issues/64)) ([7625bfc](https://github.com/Promethean-Works/athena/commit/7625bfcc28e6cff7a489077029bdb1e9b73c3636))
* **assistant:** add the Google Vertex AI provider ([#243](https://github.com/Promethean-Works/athena/issues/243)) ([0956141](https://github.com/Promethean-Works/athena/commit/0956141b6aa20b1a546b321facfddc6b9ce0ba31))
* **assistant:** add the opt-in shell ([#46](https://github.com/Promethean-Works/athena/issues/46)) ([06a9af2](https://github.com/Promethean-Works/athena/commit/06a9af25915d4fe64231610f0155137d243cdd21))
* **assistant:** compact long chats to fit each model's context window ([#60](https://github.com/Promethean-Works/athena/issues/60)) ([2fdf50e](https://github.com/Promethean-Works/athena/commit/2fdf50e4481aefaf29c305fd4004e1630ff6ac1c))
* **assistant:** delegate read-only look-ups to a helper, in the background if asked ([#67](https://github.com/Promethean-Works/athena/issues/67)) ([e60122a](https://github.com/Promethean-Works/athena/commit/e60122a946cdf4989fe5f6d9ce805e285b9da3cf))
* **assistant:** detect local AI servers on the host ([#207](https://github.com/Promethean-Works/athena/issues/207)) ([563cd2b](https://github.com/Promethean-Works/athena/commit/563cd2bc68c61ab702ef6571d608c8c094c96974))
* **assistant:** double-check answers and run workflows of read-only helpers ([#69](https://github.com/Promethean-Works/athena/issues/69)) ([59a470e](https://github.com/Promethean-Works/athena/commit/59a470ed2bfc82bf7165d7373f1b62594dd44627))
* **assistant:** generate chat titles with a model ([#43](https://github.com/Promethean-Works/athena/issues/43)) ([f513172](https://github.com/Promethean-Works/athena/commit/f513172c4fa79dd336aac4f68a47d1b709e1f7f8))
* **assistant:** list every pydantic-ai-compatible models.dev provider ([#202](https://github.com/Promethean-Works/athena/issues/202)) ([8ea285b](https://github.com/Promethean-Works/athena/commit/8ea285ba359f73b1501ce11a1db4c1b8ffda2b07))
* **assistant:** more local AI servers and custom providers ([#205](https://github.com/Promethean-Works/athena/issues/205)) ([67a52eb](https://github.com/Promethean-Works/athena/commit/67a52ebd7017ec0ab2c8d538f05d09003a373aaf))
* **assistant:** open the assistant in a side sheet from any page ([#50](https://github.com/Promethean-Works/athena/issues/50)) ([5f122b7](https://github.com/Promethean-Works/athena/commit/5f122b73d1b732ed2e60483fa7cd18a8ac90624b))
* **assistant:** persist turns, search history and externalize media (M7 D stage 2 PR 5) ([#73](https://github.com/Promethean-Works/athena/issues/73)) ([58bc48d](https://github.com/Promethean-Works/athena/commit/58bc48db5fde5f54ca62abfc69f87c1c00004b72))
* **assistant:** repair tool arguments, nudge loops and spill big tool output ([#59](https://github.com/Promethean-Works/athena/issues/59)) ([e9e30c9](https://github.com/Promethean-Works/athena/commit/e9e30c90d6b6ff8ce8e8ba19b4d480296b2d77b2))
* **assistant:** route coding-stack shell through ShellGuard + approval ([#86](https://github.com/Promethean-Works/athena/issues/86)) ([ee3d07b](https://github.com/Promethean-Works/athena/commit/ee3d07bbb5638202debddc9ce25b9d87f73df3e1))
* **assistant:** run the shell on pydantic-ai-harness, with WSL on Windows ([#47](https://github.com/Promethean-Works/athena/issues/47)) ([4dcc516](https://github.com/Promethean-Works/athena/commit/4dcc51691c206b0f84f311e109af39a2c757d128))
* **assistant:** searchable Add provider picker ([#200](https://github.com/Promethean-Works/athena/issues/200)) ([d3ee90b](https://github.com/Promethean-Works/athena/commit/d3ee90bad42d792f8da39747f812202629d25b05))
* **assistant:** show a chat's spend and keep the limit honest ([#45](https://github.com/Promethean-Works/athena/issues/45)) ([276ea5f](https://github.com/Promethean-Works/athena/commit/276ea5ffa6549dd7abf53ec123408212237aa499))
* **assistant:** use models.dev cache for dynamic AI providers ([#126](https://github.com/Promethean-Works/athena/issues/126)) ([cbe5132](https://github.com/Promethean-Works/athena/commit/cbe5132bdd6c09495643f30976271043e90376c5))
* **assistant:** wire turns into pgtask tasks for durable execution (M7 D.6) ([#83](https://github.com/Promethean-Works/athena/issues/83)) ([a82899e](https://github.com/Promethean-Works/athena/commit/a82899e2dcac549d323dbf1ab572b9217e2f6276))
* **assistant:** withhold prompt injection and redact secrets in tool results ([#62](https://github.com/Promethean-Works/athena/issues/62)) ([b2ee342](https://github.com/Promethean-Works/athena/commit/b2ee34269931458815a66cf23ebec03c112309ed))
* **automation:** add Automation UI page ([#114](https://github.com/Promethean-Works/athena/issues/114)) ([75642a5](https://github.com/Promethean-Works/athena/commit/75642a5f590e32ef4f3d14f1e4457b9a70d8aa7b))
* **backup:** add destinations, restic download and the backup capability ([#216](https://github.com/Promethean-Works/athena/issues/216)) ([9b91256](https://github.com/Promethean-Works/athena/commit/9b912567b026bc6cef18fcab5404d4e42c94180d))
* **backup:** add snapshots and plans ([#244](https://github.com/Promethean-Works/athena/issues/244)) ([59571e0](https://github.com/Promethean-Works/athena/commit/59571e07035f4fac2805b7268c14239ab6ae8eb4))
* **backup:** Backups page, destinations, plans and app tab ([#255](https://github.com/Promethean-Works/athena/issues/255)) ([14051e1](https://github.com/Promethean-Works/athena/commit/14051e1d4bce31bdc6b41e358384ae6875f32c37))
* **backup:** part 4 — named volumes, bind mounts, schedule, backup.run action, dashboard card ([#256](https://github.com/Promethean-Works/athena/issues/256)) ([294c7cc](https://github.com/Promethean-Works/athena/commit/294c7cca980233d2131edb3eb572f3b520d3959d))
* **backup:** part 5 — disaster recovery ([#259](https://github.com/Promethean-Works/athena/issues/259)) ([ddf28b5](https://github.com/Promethean-Works/athena/commit/ddf28b58a94d39510a4e30a730dd360dc83f7757))
* **backup:** part 5 — disaster recovery (restore from first-run, CLI, version check) ([#271](https://github.com/Promethean-Works/athena/issues/271)) ([f51ce42](https://github.com/Promethean-Works/athena/commit/f51ce426ba6786ebc8dcf3a4f2b24f77e6995298))
* **backup:** rclone destinations ([#253](https://github.com/Promethean-Works/athena/issues/253)) ([d1330e4](https://github.com/Promethean-Works/athena/commit/d1330e46bab011702e3fd51ac5783d3465c46673))
* **backup:** restore one app from a version ([#251](https://github.com/Promethean-Works/athena/issues/251)) ([9e8527c](https://github.com/Promethean-Works/athena/commit/9e8527c4ea68772d95ff09f9e9ae80d61088b602))
* **backup:** retention, prune, check and the versions listing ([#247](https://github.com/Promethean-Works/athena/issues/247)) ([17962a2](https://github.com/Promethean-Works/athena/commit/17962a26b8f754bd59aaea8ce29095130bec2cc3))
* **catalog:** add a runtime smoke test that installs store apps for real ([#169](https://github.com/Promethean-Works/athena/issues/169)) ([d5d5ddd](https://github.com/Promethean-Works/athena/commit/d5d5ddd1ec44310b96f819431ce5d7ad2bdfe820))
* **catalog:** add database-backend select to FreshRSS ([#135](https://github.com/Promethean-Works/athena/issues/135)) ([5cb0bd8](https://github.com/Promethean-Works/athena/commit/5cb0bd8238c6778744336d18dcefa08c8b5a0387))
* **catalog:** support installable compose variants per store app ([#109](https://github.com/Promethean-Works/athena/issues/109)) ([59fa45c](https://github.com/Promethean-Works/athena/commit/59fa45c5e4735307c81adf18b090c459fb8ca6f6))
* **cli:** add start, stop, doctor and config subcommands ([#112](https://github.com/Promethean-Works/athena/issues/112)) ([6601bfc](https://github.com/Promethean-Works/athena/commit/6601bfc772e2c984a61eca8ae3922714e108b14e))
* **cli:** server settings in athena.json and athena config path/show/check/reset ([#209](https://github.com/Promethean-Works/athena/issues/209)) ([22c81ce](https://github.com/Promethean-Works/athena/commit/22c81ce17fbf3114fe9a0204c97a370c676da706))
* **cloud:** add rclone remotes, browsing and copy/sync jobs ([#35](https://github.com/Promethean-Works/athena/issues/35)) ([1cf543f](https://github.com/Promethean-Works/athena/commit/1cf543fe0041a99e22db210cf51ebe83aaf5c916))
* **cloud:** add-storage wizard with provider catalog ([#97](https://github.com/Promethean-Works/athena/issues/97)) ([b87b8ae](https://github.com/Promethean-Works/athena/commit/b87b8ae5bdecdf8753459c3aa27d0a1583547210))
* **cloud:** friendlier cloud page with remote cards ([#92](https://github.com/Promethean-Works/athena/issues/92)) ([b9ab0d0](https://github.com/Promethean-Works/athena/commit/b9ab0d0489d2619bb50c8a216507b72f4e99a5a3))
* container runtime, jobs and containers page (M2 part A) ([#15](https://github.com/Promethean-Works/athena/issues/15)) ([ac75134](https://github.com/Promethean-Works/athena/commit/ac75134f013ac5852e0e2f3aa20b2cca0be6cf5b))
* **dashboard:** add containers, automation, recent activity and remote access cards ([#183](https://github.com/Promethean-Works/athena/issues/183)) ([25f3cc2](https://github.com/Promethean-Works/athena/commit/25f3cc2640f5bb7261010f9152ac1e4de67bcce9))
* **dashboard:** app grid with status, Open and start/stop (M4 part 2) ([#21](https://github.com/Promethean-Works/athena/issues/21)) ([6fc9bb6](https://github.com/Promethean-Works/athena/commit/6fc9bb6a68243b4589d38fdc810f821a8a356ef9))
* **dashboard:** app icon opens app, dots on icon with Settings, remove container count ([#153](https://github.com/Promethean-Works/athena/issues/153)) ([d8acc8b](https://github.com/Promethean-Works/athena/commit/d8acc8bc1628816c5f34a47d020fa3e1171ecfa5))
* **dashboard:** live host stats with sparklines (M4 part 1) ([#20](https://github.com/Promethean-Works/athena/issues/20)) ([d779f7f](https://github.com/Promethean-Works/athena/commit/d779f7f8adfa6da43c0050fab58b254830ac7e3f))
* **dashboard:** redesign app grid in CasaOS style ([#146](https://github.com/Promethean-Works/athena/issues/146)) ([1cb3c54](https://github.com/Promethean-Works/athena/commit/1cb3c54aaf8e763490b9cc62018f22febc133c70))
* **dashboard:** save each user's dashboard layout and list the audit log ([#181](https://github.com/Promethean-Works/athena/issues/181)) ([72e419b](https://github.com/Promethean-Works/athena/commit/72e419b5877d572f672251be8e2379fb8c547039))
* **dashboard:** show apps as icon grid instead of list ([#145](https://github.com/Promethean-Works/athena/issues/145)) ([6292e9f](https://github.com/Promethean-Works/athena/commit/6292e9f72c1455c9714734ebadbcd0cbaeb5bdb2))
* **feedback:** report bugs, changes, features and broken store apps from the UI ([#170](https://github.com/Promethean-Works/athena/issues/170)) ([d5f9eb5](https://github.com/Promethean-Works/athena/commit/d5f9eb5476d3a126efe2a40f0d7cf5f9e1b47f57))
* **files:** file manager with locations, uploads and previews (M6 part A) ([#25](https://github.com/Promethean-Works/athena/issues/25)) ([9d88a27](https://github.com/Promethean-Works/athena/commit/9d88a27bd631c612609c010b77fe0fb4962787d4))
* first-run setup, admin login and session auth (M1 part 2) ([#12](https://github.com/Promethean-Works/athena/issues/12)) ([c1af5ae](https://github.com/Promethean-Works/athena/commit/c1af5ae6d1f69c6c35cd43494d1da4cc805c8c30))
* host capability detection and capability-gated UI (M1 part 1) ([#11](https://github.com/Promethean-Works/athena/issues/11)) ([b24f280](https://github.com/Promethean-Works/athena/commit/b24f2801c6e1a2f4975625a7e211bd01745283ca))
* **https:** add custom certificate upload mode ([#267](https://github.com/Promethean-Works/athena/issues/267)) ([0a06cf7](https://github.com/Promethean-Works/athena/commit/0a06cf7f4e7a2aab21040e0d0c3a8e519a76dca9))
* **https:** add the Settings → HTTPS page ([#196](https://github.com/Promethean-Works/athena/issues/196)) ([c467f45](https://github.com/Promethean-Works/athena/commit/c467f45cbd5b86a5d9d3268b56f6d91285695271))
* **https:** get and renew Let's Encrypt certificates with lego ([#199](https://github.com/Promethean-Works/athena/issues/199)) ([0bb6f0a](https://github.com/Promethean-Works/athena/commit/0bb6f0a69e8fea188e49358c341a8b9e61a5de1f))
* **https:** serve Athena over HTTPS with a self-signed local CA ([#192](https://github.com/Promethean-Works/athena/issues/192)) ([3764d5f](https://github.com/Promethean-Works/athena/commit/3764d5f061df9a2645ec5cd085f27faebb5aae6a))
* **mcp:** add github MCP server to all agent configs ([#254](https://github.com/Promethean-Works/athena/issues/254)) ([8e86ec7](https://github.com/Promethean-Works/athena/commit/8e86ec74dd4d602ac041768a7cee56a1ab945c8f))
* monorepo skeleton with web shell, server, API client and release build (M0) ([#4](https://github.com/Promethean-Works/athena/issues/4)) ([8b3fbd4](https://github.com/Promethean-Works/athena/commit/8b3fbd4ef989915a2eb617c9149565389b25028e))
* **packages:** package managers for Linux, macOS and Windows (M5 part A) ([#23](https://github.com/Promethean-Works/athena/issues/23)) ([6b7172d](https://github.com/Promethean-Works/athena/commit/6b7172d194fb04f0de18ec4331cca97ff16a13af))
* **pi-memory:** lazy-load assistant stack to reduce Raspberry Pi memory ([#265](https://github.com/Promethean-Works/athena/issues/265)) ([36d9177](https://github.com/Promethean-Works/athena/commit/36d9177d599e42a217ef4630143379d156af74a2))
* remote catalogs, CasaOS AppStore import and app settings editing (M3 part B) ([#18](https://github.com/Promethean-Works/athena/issues/18)) ([0e49496](https://github.com/Promethean-Works/athena/commit/0e49496069d699e010557a62f8b2a45d87d83454))
* **server:** `athena admin reset-password` for admin account recovery ([#13](https://github.com/Promethean-Works/athena/issues/13)) ([0694102](https://github.com/Promethean-Works/athena/commit/069410214cd20572a50ac4a62174bf63cf9203b7))
* **server:** add GPU and VRAM to host stats monitoring ([#93](https://github.com/Promethean-Works/athena/issues/93)) ([412a59e](https://github.com/Promethean-Works/athena/commit/412a59eedf83ff8a0d4ab6544d5cbd1e19b90c8d))
* **settings:** runtime appearance and password change (M4 part 3) ([#22](https://github.com/Promethean-Works/athena/issues/22)) ([db44924](https://github.com/Promethean-Works/athena/commit/db44924ad295dfa25ed86c78a51ec08ab9240acc))
* **settings:** store host-wide settings in athena.json ([#204](https://github.com/Promethean-Works/athena/issues/204)) ([6282c10](https://github.com/Promethean-Works/athena/commit/6282c107ced3245150693b567bc83ccb02cb5e50))
* **shares:** add a web UI for SMB shares ([#104](https://github.com/Promethean-Works/athena/issues/104)) ([dcd06fa](https://github.com/Promethean-Works/athena/commit/dcd06fa579dd04609ee394df5b6fdc83332ece47))
* **shares:** add SMB shares for the installed server ([#95](https://github.com/Promethean-Works/athena/issues/95)) ([0e4c19a](https://github.com/Promethean-Works/athena/commit/0e4c19adda787399102d87365e91988ce8681243))
* **shares:** share links and WebDAV (M6 part B) ([#28](https://github.com/Promethean-Works/athena/issues/28)) ([57341ca](https://github.com/Promethean-Works/athena/commit/57341caee3701ac1fcbefe84d601659e72c17882))
* **store:** add 29 apps and make the store look like a store ([#98](https://github.com/Promethean-Works/athena/issues/98)) ([a7dd848](https://github.com/Promethean-Works/athena/commit/a7dd84813654321c75827e6327a09ad735c4f804))
* **store:** add AI, databases, notes, finance, reading and documents categories ([#208](https://github.com/Promethean-Works/athena/issues/208)) ([cb798ea](https://github.com/Promethean-Works/athena/commit/cb798ea534893ea0efcbb1b5e97fcdafac50bd01))
* **store:** filter apps by the host's CPU architecture ([#165](https://github.com/Promethean-Works/athena/issues/165)) ([1e1f836](https://github.com/Promethean-Works/athena/commit/1e1f8369e8a2912e0c94007503f1028ece52141c))
* **store:** import CasaOS AppStore apps into the catalog ([#120](https://github.com/Promethean-Works/athena/issues/120)) ([1dc0a65](https://github.com/Promethean-Works/athena/commit/1dc0a6512061a875925e9571e06bfc798cc3a2f9))
* **store:** port CasaOS apps and add catalog screenshots ([#106](https://github.com/Promethean-Works/athena/issues/106)) ([f63b6a6](https://github.com/Promethean-Works/athena/commit/f63b6a66665fd75a4fccc9030b35e8f914fd85ca))
* **store:** redesign the popular-right-now carousel ([#177](https://github.com/Promethean-Works/athena/issues/177)) ([10d991c](https://github.com/Promethean-Works/athena/commit/10d991cef52dde69f477733732b4e4be30471646))
* **store:** replace the popular-right-now strip with an autoplay carousel ([#103](https://github.com/Promethean-Works/athena/issues/103)) ([7aeb3a7](https://github.com/Promethean-Works/athena/commit/7aeb3a7b47caec73d0e3492515798368042ee7a7))
* **system:** add Restart Athena ([#215](https://github.com/Promethean-Works/athena/issues/215)) ([daed95a](https://github.com/Promethean-Works/athena/commit/daed95ae97d8401767a9aae293270077ea3a515d))
* **terminal:** host terminal and container shells (M5 part B) ([#24](https://github.com/Promethean-Works/athena/issues/24)) ([5b3f097](https://github.com/Promethean-Works/athena/commit/5b3f0979d28b8f3273f015ec8b856bcf6ccc32ee))
* **tooling:** add frontend-design skill and design-quality rules ([#100](https://github.com/Promethean-Works/athena/issues/100)) ([96877ff](https://github.com/Promethean-Works/athena/commit/96877ff09e21167bc34a2415ebf88853c474685a))
* **tunnel:** add remote access tunnel support with Cloudflare, Tailscale, Ngrok ([#128](https://github.com/Promethean-Works/athena/issues/128)) ([882d9f1](https://github.com/Promethean-Works/athena/commit/882d9f1f9f2c44f66aea17c17372d0b9cb29f0a6))
* update notice and Raspberry Pi health ([#242](https://github.com/Promethean-Works/athena/issues/242)) ([de37aec](https://github.com/Promethean-Works/athena/commit/de37aec78fdb4e61e46f25eb7b33bf3ca9f908a9))
* **update:** athena update with a rollback helper ([#246](https://github.com/Promethean-Works/athena/issues/246)) ([4a10721](https://github.com/Promethean-Works/athena/commit/4a107219ebd6ffdb5247444ee3db69759a978462))
* **update:** back up Athena first and warn about an interrupted update ([#284](https://github.com/Promethean-Works/athena/issues/284)) ([7fb1a3e](https://github.com/Promethean-Works/athena/commit/7fb1a3edda6248576384435c1fc31ec623cdd0c3))
* **update:** start the update helper from the server ([#250](https://github.com/Promethean-Works/athena/issues/250)) ([02284c0](https://github.com/Promethean-Works/athena/commit/02284c00dc8a442f5b554564b5b05e6772e22ff1))
* **update:** update status, audit, rate limit and the Update Athena UI ([#252](https://github.com/Promethean-Works/athena/issues/252)) ([ec305ff](https://github.com/Promethean-Works/athena/commit/ec305ff6519343951b16c1bdff39ac637f825b39))
* **web:** add the AI assistant step to the setup wizard ([#58](https://github.com/Promethean-Works/athena/issues/58)) ([06e5a0e](https://github.com/Promethean-Works/athena/commit/06e5a0ed828abb6fa7e85c7d78cad8b8e75e1284))
* **web:** show where settings are saved on Settings → System ([#210](https://github.com/Promethean-Works/athena/issues/210)) ([fd9c903](https://github.com/Promethean-Works/athena/commit/fd9c903f15bd90074850e6f867be627a97d12323))


### Bug Fixes

* **agents:** escape all regex characters when matching Hermes MCP servers ([#14](https://github.com/Promethean-Works/athena/issues/14)) ([035e6fe](https://github.com/Promethean-Works/athena/commit/035e6fe51a4f7451ac8d1eb1350503806da6cbf2))
* **agents:** let the base checkout fast-forward to origin/main during runs ([#283](https://github.com/Promethean-Works/athena/issues/283)) ([a4f90f1](https://github.com/Promethean-Works/athena/commit/a4f90f1424d6696bcc7a17d29ac06f2a037ad217))
* **agents:** require a worktree per task and enforce it in pre-commit ([#122](https://github.com/Promethean-Works/athena/issues/122)) ([e78db69](https://github.com/Promethean-Works/athena/commit/e78db691dca37735fd0b961be095606743eb3ba5))
* **agents:** verify against a base-commit baseline, quick mode, flaky tunnel test ([#275](https://github.com/Promethean-Works/athena/issues/275)) ([5431e85](https://github.com/Promethean-Works/athena/commit/5431e859fe8648f892195160568b624cd1800cf0))
* **apps:** fix infinite render loop in ComposeForm NetworksTab/VolumesTab ([#140](https://github.com/Promethean-Works/athena/issues/140)) ([bde92a2](https://github.com/Promethean-Works/athena/commit/bde92a27d443df8ce7f8fc23c37bcb004f64eb22))
* **apps:** stop ComposeForm form/YAML sync loop ([#143](https://github.com/Promethean-Works/athena/issues/143)) ([59c8135](https://github.com/Promethean-Works/athena/commit/59c81359a1f76e2ed381486585920d1486128458))
* **assistant:** audit actions denied by a new message ([#42](https://github.com/Promethean-Works/athena/issues/42)) ([17e4ad1](https://github.com/Promethean-Works/athena/commit/17e4ad1aa53bed569d1160fedb379e3e939404ad))
* **assistant:** generate chat title sequentially after turn to avoid 409 ([#124](https://github.com/Promethean-Works/athena/issues/124)) ([90d220e](https://github.com/Promethean-Works/athena/commit/90d220e3cf6c2509a2249024e9ea984afabff60b))
* **assistant:** install cohere extra and map MCP token to admin ([#149](https://github.com/Promethean-Works/athena/issues/149)) ([3637b4a](https://github.com/Promethean-Works/athena/commit/3637b4a8a815ac60281a0b06ab545bf1ade999e8))
* **assistant:** load models.dev provider kinds ([#197](https://github.com/Promethean-Works/athena/issues/197)) ([ceb0656](https://github.com/Promethean-Works/athena/commit/ceb0656eed38d1bde33cbe0cedee27eed237adb7))
* **assistant:** make request and tool-call limits per turn ([#44](https://github.com/Promethean-Works/athena/issues/44)) ([fccccc8](https://github.com/Promethean-Works/athena/commit/fccccc81b0b312a9c52132ac07c3bed49a8eedb2))
* **assistant:** queue local AI calls and name chats outside the turn ([#142](https://github.com/Promethean-Works/athena/issues/142)) ([907d99f](https://github.com/Promethean-Works/athena/commit/907d99f280aa043eea0466c9e200fa41230c9411))
* **automation:** fix nested button in DialogTrigger ([#136](https://github.com/Promethean-Works/athena/issues/136)) ([3d91273](https://github.com/Promethean-Works/athena/commit/3d91273a419a6dad4d3d27a69b61f8321436e778))
* **automation:** keep SQLite writes off the event loop when a trigger fires ([#229](https://github.com/Promethean-Works/athena/issues/229)) ([181e2a0](https://github.com/Promethean-Works/athena/commit/181e2a0005966422e6c9a4221598edece33ae68b))
* **automation:** tidy the page and make the trigger form easier ([#179](https://github.com/Promethean-Works/athena/issues/179)) ([9eb7b98](https://github.com/Promethean-Works/athena/commit/9eb7b98386a0412c04d3061c19db4839a80a6f89))
* **catalog:** drop proprietary apps, skip handbrake smoke, stop hard-coding /DATA paths ([#186](https://github.com/Promethean-Works/athena/issues/186)) ([5a1628f](https://github.com/Promethean-Works/athena/commit/5a1628f17336e10cd5a311a97f559afd61998efb))
* **catalog:** fix data folder permissions for 2fauth, labelstudio, pdfding and langflow ([#214](https://github.com/Promethean-Works/athena/issues/214)) ([1f11c76](https://github.com/Promethean-Works/athena/commit/1f11c76444bf2500a4633c8c212953f37465d71a))
* **catalog:** keep the smoke test from filling the disk or touching the repo ([#172](https://github.com/Promethean-Works/athena/issues/172)) ([d261369](https://github.com/Promethean-Works/athena/commit/d261369147e60dfbd1448b465564b9342f8c3da9))
* **catalog:** let the smoke workflow upload its report on Linux ([#178](https://github.com/Promethean-Works/athena/issues/178)) ([7658885](https://github.com/Promethean-Works/athena/commit/7658885cd6b07a9e0a22c1509cdf72e74424fc1c))
* **catalog:** make 15 store apps start (smoke test batch A) ([#175](https://github.com/Promethean-Works/athena/issues/175)) ([2ae1c50](https://github.com/Promethean-Works/athena/commit/2ae1c5098e73eb33847fb406ef1935d3a7d9848f))
* **catalog:** make 15 store apps start (smoke test batch B) ([#174](https://github.com/Promethean-Works/athena/issues/174)) ([ead1e52](https://github.com/Promethean-Works/athena/commit/ead1e526c24515745b612eccdab80e2c5fe13f7a))
* **catalog:** make 16 store apps start (smoke test batch C) ([#173](https://github.com/Promethean-Works/athena/issues/173)) ([c3c4091](https://github.com/Promethean-Works/athena/commit/c3c4091825c42d257170e50b61e0d58e05d2a37b))
* **catalog:** mark store apps a test machine can't run and fix amd64-only pulls ([#176](https://github.com/Promethean-Works/athena/issues/176)) ([3e886cf](https://github.com/Promethean-Works/athena/commit/3e886cf2a5c97c3aac277e363a406ff34754b3f4))
* **catalog:** pin 60+ app versions, fix icons, healthchecks, DB passwords, depends_on ([#139](https://github.com/Promethean-Works/athena/issues/139)) ([ba807cf](https://github.com/Promethean-Works/athena/commit/ba807cf172719c8e409c17945edc3aed14350981))
* **catalog:** remove duplicate chatgpt-next-web, pingvin-share and siyuan-note apps ([#212](https://github.com/Promethean-Works/athena/issues/212)) ([ecb5e81](https://github.com/Promethean-Works/athena/commit/ecb5e81b5ca0296a697cf2be3bee0bbb5209bfe7))
* **catalog:** remove the remaining proprietary apps ([#193](https://github.com/Promethean-Works/athena/issues/193)) ([25d6e7d](https://github.com/Promethean-Works/athena/commit/25d6e7d065f1a1d64c9914c7b8a15d98c3748539))
* **catalog:** repair apps with broken images and generate their secrets per install ([#167](https://github.com/Promethean-Works/athena/issues/167)) ([4dcdda1](https://github.com/Promethean-Works/athena/commit/4dcdda1db28f50c5799a0285f04d46155faa34a4))
* **containers:** start docker with stdin=DEVNULL to avoid WinError 6 ([#224](https://github.com/Promethean-Works/athena/issues/224)) ([3fcfe94](https://github.com/Promethean-Works/athena/commit/3fcfe94504c031363e5099c0d95721912a718067))
* **e2e:** self-update job reads the update state as root ([#249](https://github.com/Promethean-Works/athena/issues/249)) ([7e74a90](https://github.com/Promethean-Works/athena/commit/7e74a90f645157d857b17d53cf82d2b796e76bcd))
* **e2e:** skip the optional AI setup step in the smoke test ([#90](https://github.com/Promethean-Works/athena/issues/90)) ([e004f71](https://github.com/Promethean-Works/athena/commit/e004f710aa146f8ace3030149f1c11dc8aa36e60))
* **e2e:** wait for the server before the self-update check ([#248](https://github.com/Promethean-Works/athena/issues/248)) ([8ad0874](https://github.com/Promethean-Works/athena/commit/8ad08743685a84bb55fec7825b7e4cef570a1823))
* **https:** check port 80 before lego runs, and test HTTPS on real hosts ([#203](https://github.com/Promethean-Works/athena/issues/203)) ([39f7a7e](https://github.com/Promethean-Works/athena/commit/39f7a7e27fb0ea83aa9e4a4c60dc463c04294b84))
* **https:** keep the last renewal result and error across restarts ([#228](https://github.com/Promethean-Works/athena/issues/228)) ([cc4dd1c](https://github.com/Promethean-Works/athena/commit/cc4dd1c9045b708e386343850c4e533302d412a5))
* **installers:** fetch pre-release wheels and let E2E smoke a published release ([#285](https://github.com/Promethean-Works/athena/issues/285)) ([5e92d09](https://github.com/Promethean-Works/athena/commit/5e92d0912ee1421fecb6a64ff070e6d01648efea))
* **install:** satisfy PSScriptAnalyzer and dry-run uninstall in CI ([#1](https://github.com/Promethean-Works/athena/issues/1)) ([5c0f11f](https://github.com/Promethean-Works/athena/commit/5c0f11ff0308b200236af81376faf630a8423492))
* **install:** stop on a 32-bit userland under a 64-bit kernel ([#158](https://github.com/Promethean-Works/athena/issues/158)) ([be89900](https://github.com/Promethean-Works/athena/commit/be899009604cbd3bc772ad3bb7be474a7217c679))
* **monitor:** stop sampling when the loop's executor shuts down ([#111](https://github.com/Promethean-Works/athena/issues/111)) ([1fd087c](https://github.com/Promethean-Works/athena/commit/1fd087c1281e8633387d4435aafa8b12cb267c1b))
* **qa:** resolve bugs found in repo check and add e2e tests ([#94](https://github.com/Promethean-Works/athena/issues/94)) ([8716564](https://github.com/Promethean-Works/athena/commit/8716564d4be190ca4b52375d2278f7d89c2f4d46))
* **server:** stop echoing any Origin with credentials on the stats stream ([#102](https://github.com/Promethean-Works/athena/issues/102)) ([a8381ec](https://github.com/Promethean-Works/athena/commit/a8381ec48bb576737f8eecef9167413c04df128a))
* **settings:** move useCapability hooks to top level in SystemForm ([#131](https://github.com/Promethean-Works/athena/issues/131)) ([de09246](https://github.com/Promethean-Works/athena/commit/de09246237df79c96711343d3cede79fb7eddd94))
* **settings:** tidy every settings page and fix the tunnel card ([#180](https://github.com/Promethean-Works/athena/issues/180)) ([aeb895f](https://github.com/Promethean-Works/athena/commit/aeb895f58397e42a7208277fc85e5e756114063a))
* **setup:** stop rendering the account form inside the choose step ([#278](https://github.com/Promethean-Works/athena/issues/278)) ([71533b1](https://github.com/Promethean-Works/athena/commit/71533b1ccf044b636f8ae939ba487fd1989c2b64))
* start releases at 0.1.0 and patch baseline-browser-mapping ([#9](https://github.com/Promethean-Works/athena/issues/9)) ([e4a8d26](https://github.com/Promethean-Works/athena/commit/e4a8d26144c0dddc5865a464895cb2ee6195543f))
* **store:** keep StoreAppView hook order stable ([#113](https://github.com/Promethean-Works/athena/issues/113)) ([8d1768c](https://github.com/Promethean-Works/athena/commit/8d1768c63bf3b1fb4d2819d00c7cf6730dde432d))
* **store:** remove CasaOS AppStore catalog card from store UI ([#121](https://github.com/Promethean-Works/athena/issues/121)) ([b52dcab](https://github.com/Promethean-Works/athena/commit/b52dcab9bc26c65f58f9b971259b9f31f9aa59d1))
* **store:** say when a search matches hidden apps, keep installed tunnels detected ([#166](https://github.com/Promethean-Works/athena/issues/166)) ([618abc8](https://github.com/Promethean-Works/athena/commit/618abc86c07ae1f9d57a8679165397894e93ed74))
* **terminal:** keep a hidden console so ConPTY sessions don't close the server's std handles ([#206](https://github.com/Promethean-Works/athena/issues/206)) ([7f14c04](https://github.com/Promethean-Works/athena/commit/7f14c04296d82b5944ada7e8314761842655f8af))
* **terminal:** keep pty output when the reader is late on macOS ([#232](https://github.com/Promethean-Works/athena/issues/232)) ([981220e](https://github.com/Promethean-Works/athena/commit/981220ed5758f689acc6cb1a8344db7c5086ee95))
* **test:** increase context window for compaction test to accommodate new capabilities ([#138](https://github.com/Promethean-Works/athena/issues/138)) ([93a8429](https://github.com/Promethean-Works/athena/commit/93a84297e978e7df2d584592c2983463f1dc1c2f))
* **tunnel:** await job.log calls and remove non-existent set_result ([#133](https://github.com/Promethean-Works/athena/issues/133)) ([6b8d050](https://github.com/Promethean-Works/athena/commit/6b8d0504778129d54d12fe642ed8ab738827d1ee))
* **tunnel:** download the cloudflared release assets that exist ([#160](https://github.com/Promethean-Works/athena/issues/160)) ([b8f3a1a](https://github.com/Promethean-Works/athena/commit/b8f3a1af61829de1ea2e010ecf0b53682ff23ee2))
* **tunnel:** fix port field alignment and tunnel status detection ([#144](https://github.com/Promethean-Works/athena/issues/144)) ([15cbda9](https://github.com/Promethean-Works/athena/commit/15cbda9c24e6dd05a71b6bed5d1a4729a59502ec))
* **tunnel:** really start the tunnel client and track its status ([#190](https://github.com/Promethean-Works/athena/issues/190)) ([2208ef8](https://github.com/Promethean-Works/athena/commit/2208ef89a2db9d8659ed7c4b283118f46638004c))
* **tunnel:** require admin and encrypt tunnel secrets ([#150](https://github.com/Promethean-Works/athena/issues/150)) ([7de7584](https://github.com/Promethean-Works/athena/commit/7de7584af53044c8feac3a5fde0cc40a157de271))
* **tunnel:** start the tunnel at boot when auto-start is on ([#225](https://github.com/Promethean-Works/athena/issues/225)) ([7ae770c](https://github.com/Promethean-Works/athena/commit/7ae770c2fed4332c7524e32c977a2f93c2a04c3d))
* **tunnel:** write real tokens to private files for the ngrok and cloudflared services ([#230](https://github.com/Promethean-Works/athena/issues/230)) ([72462f8](https://github.com/Promethean-Works/athena/commit/72462f8498cb0d44037bb6c84982bc0ae1f9a76d))
* **ui:** remove dead switches and warn when a tunnel is on ([#223](https://github.com/Promethean-Works/athena/issues/223)) ([ecb43da](https://github.com/Promethean-Works/athena/commit/ecb43dae5733382663006fa84e5a2208209363ac))
* **ui:** set nativeButton=false on assistant sheet Link button ([#117](https://github.com/Promethean-Works/athena/issues/117)) ([960c98b](https://github.com/Promethean-Works/athena/commit/960c98b821ac4b65aabe0dc68522040e0b1bf66a))
* **ui:** set nativeButton=false on Link-rendered Buttons ([#79](https://github.com/Promethean-Works/athena/issues/79)) ([75b8aec](https://github.com/Promethean-Works/athena/commit/75b8aecf68135a71cd97df5bf8abdf234d3ab7fc))
* **ui:** set nativeButton=false on OpenLinks anchor button ([#99](https://github.com/Promethean-Works/athena/issues/99)) ([bc73e61](https://github.com/Promethean-Works/athena/commit/bc73e617539cbcd4f3a9b13c012907b39a8583b9))
* **web:** guard theme hotkey against undefined event.key ([#96](https://github.com/Promethean-Works/athena/issues/96)) ([184a3c0](https://github.com/Promethean-Works/athena/commit/184a3c0bc1feab86e29b1241493ac3bf4b5a92b6))
* **web:** lint .tsx files and fix what it reports ([#233](https://github.com/Promethean-Works/athena/issues/233)) ([132400c](https://github.com/Promethean-Works/athena/commit/132400cb0b6c4076ccfd0794122b1c4c401e04bd))
* **web:** type children on ThemeProvider wrapper ([#119](https://github.com/Promethean-Works/athena/issues/119)) ([4586704](https://github.com/Promethean-Works/athena/commit/4586704ec53ce07d1780f1af1b14cf6ee0cef821))


### Performance Improvements

* **server:** load the assistant and MCP stacks on first use ([#161](https://github.com/Promethean-Works/athena/issues/161)) ([7808236](https://github.com/Promethean-Works/athena/commit/78082360f0fe0c94c1009f5a78039f15a01d5a44))

## Changelog

All notable changes to Athena are documented here. This file is generated by
[release-please](https://github.com/googleapis/release-please) from the
[Conventional Commit](https://www.conventionalcommits.org) titles of merged pull requests.
Don't edit it by hand. Release-please adds a section for each release, and unreleased changes
appear in the open release pull request. See [CONTRIBUTING.md](CONTRIBUTING.md#releases).
