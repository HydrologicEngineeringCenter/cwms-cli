# Changelog

## [0.8.0](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.7.4...v0.8.0) (2026-08-06)


### Features

* Add modern DSS transfer utilities ([#242](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/242)) ([89e01f4](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/89e01f48231d084a7989319f82d5d08d4137d940))
* allow for line return tsid parsing ([#230](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/230)) ([39f7f6b](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/39f7f6be090201368f7e203edf8a80174721b1f5))
* display CDA server stack traces in debug mode ([#247](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/247)) ([c3bfcf9](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/c3bfcf92b2f04b125a56a1d106fda07b26e21091))


### Bug Fixes

* align formatting checks ([#229](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/229)) ([a6286b3](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/a6286b3d299545a587483aa68b2f68d4da57c5cc))
* cover explicit blob media type ([#232](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/232)) ([1a3b26d](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/1a3b26dfeab07cd0030c59eea60f65d4608e2faa))
* explain empty location loads ([#233](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/233)) ([a5b596c](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/a5b596c4be1ba3ba0c62b4fadb2abb7e2d48329e))
* harden clob download error handling ([#235](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/235)) ([621f913](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/621f9139eb28991d38bc93665428798189f02887))
* Improve version issue error message in deps.py ([#245](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/245)) ([f77b75f](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/f77b75f23782c200a5b6e35419937483aab675d1))
* refresh ownership metadata ([#251](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/251)) ([3b31479](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/3b31479d18f326c467eef4b4074c9b6a266b46e1))
* show update environment before confirmation ([#246](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/246)) ([500435c](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/500435c9eb1eb283424cb3071de99d851f59951d)), closes [#222](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/222)
* validate blob list limits ([#231](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/231)) ([0917ce9](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/0917ce9ce133b48168b3d4ddb189b1887d63e6eb))
* validate load target cda ([#236](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/236)) ([ff3e06a](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/ff3e06a22825a0d4f7b4d7b2653085d464118fe2))
* wait for auth callback server readiness ([#249](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/249)) ([ca39d5b](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/ca39d5bebb437eb1b715f5f6c0dc703116ad02fd))


### Documentation

* guide agents to shared color helpers ([#248](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/248)) ([ef03276](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/ef0327653a6b8b3220ff79d0e6162056c6ddaf27))

## [0.7.4](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.7.3...v0.7.4) (2026-06-25)


### Bug Fixes

* add failback for shef infile import when tsid doesn't exist ([#218](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/218)) ([77172d2](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/77172d247e191605e27f96b04f0d9495929b2ffd))
* github vulnerabilities (urllib, idna, pytest, black, requests, filelock, pytest) ([#223](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/223)) ([0935234](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/09352345c7b95317dbb8888ebe46f5461c383a32))

## [0.7.3](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.7.2...v0.7.3) (2026-06-04)


### Bug Fixes

* Import logging module in timeseries_ids.py ([#219](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/219)) ([5ce62bb](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/5ce62bb38678440b1bc053cdb8c30e44a794b63b))

## [0.7.2](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.7.1...v0.7.2) (2026-05-13)


### Bug Fixes

* update shef infile importer to handle nwo infiles ([#216](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/216)) ([7da15b3](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/7da15b34864f76db0eacf8459682c75cf941fab4))

## [0.7.1](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.7.0...v0.7.1) (2026-05-05)


### Bug Fixes

* Issue 195 path safety tests ([#203](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/203)) ([595bf22](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/595bf225e3d50cf59f362516793f1957408b5b39))

## [0.7.0](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.6.0...v0.7.0) (2026-04-30)


### Features

* add function to save and load locations to csv file ([#213](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/213)) ([2668ab0](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/2668ab0faac239b8f7088b631656002bd9643515))

## [0.6.0](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.5.0...v0.6.0) (2026-04-28)


### Features

* 79 standard login should be supported ([#155](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/155)) ([35d0180](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/35d0180180219459065d4d4cf39c975e669182eb))
* Add shef in file export, update shef command ([#196](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/196)) ([4b3e0bf](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/4b3e0bf5e40490689446722db73a0923f8ad0fa4))


### Bug Fixes

* 158 add smart complete feature to the cli ([#178](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/178)) ([e755cc9](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/e755cc932adfbfa334937c4c4cd8020848453009))
* Fix blob-id path for delete ([#201](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/201)) ([bbfb87d](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/bbfb87d631f4cedb3e21946ea218013d99cb4dd2))
* Update ini import ([#212](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/212)) ([b02eb8d](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/b02eb8da38a88308e9ebc19d024e42d2a6cb556a))

## [0.5.0](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.4.0...v0.5.0) (2026-04-09)


### Features

* Centralized maintainer ownership for CLI help and docs           ([#180](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/180)) ([ba722a1](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/ba722a13dfe835ebb67ee0916d6d0b42f9a5de62))
* Enhancements/clob ([#73](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/73)) ([29f43dc](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/29f43dcd5371bc97089064424769df20979092b0))
* Timeseries Loader ([#137](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/137)) ([9a120e3](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/9a120e378049eebcd2c3bfd9e57748ae171a767c))


### Bug Fixes

* 184 blob list   limit doesnt work ([#188](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/188)) ([f1b631b](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/f1b631b94e94e80703b1f2d5c05f35126b32c4cc))
* removed | operators ([#191](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/191)) ([8092c4b](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/8092c4b9ef1fbe6fab7cbc71cddc25f75aaf720d))

## [0.4.0](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.3.8...v0.4.0) (2026-04-02)


### Features

* 45 users cli ([#147](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/147)) ([08ae2a4](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/08ae2a45dbc7a3d945d056a1dda991c641a1743e))

## [0.3.8](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.3.7...v0.3.8) (2026-03-30)


### Bug Fixes

* 108 issue passing  kl into cwms cli ([#170](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/170)) ([2d4d63e](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/2d4d63e5e2c2007ee74b1da042cfbca8dfe93cc5))
* Add and test for friendly user error output on usgs ts command ([#177](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/177)) ([9b7886a](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/9b7886a0018eb90566d35d5d43fdc4223c8a75a5))

## [0.3.7](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.3.6...v0.3.7) (2026-03-28)


### Bug Fixes

* 128 add warningdisplay that there is a newer version avaiable ([#174](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/174)) ([b6a66df](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/b6a66dfceee39e9189a2f09f3f36008d7ae24b12))
* 140 allow version target on update command ([#171](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/171)) ([407af1f](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/407af1f8695885c155660503798e85c8b243932c))
* 51 change default precision case for csv2cwms ([#173](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/173)) ([fabf94e](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/fabf94ec6340724cf2a42797cf58aee342de62db))
* 81 graceful error handling ([#176](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/176)) ([2dd6356](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/2dd6356a7db32074f4d49be33cb70101cc817a95))
* Avoid circular reference failures in doc site ([#175](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/175)) ([fa8dc68](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/fa8dc68f7a2e139d6b0d5e2dcff3deb790552349))

## [0.3.6](https://github.com/HydrologicEngineeringCenter/cwms-cli/compare/v0.3.5...v0.3.6) (2026-03-27)


### Bug Fixes

* missing space and add test ([#167](https://github.com/HydrologicEngineeringCenter/cwms-cli/issues/167)) ([7f0da1f](https://github.com/HydrologicEngineeringCenter/cwms-cli/commit/7f0da1f20552ae50d2142af496a63095d0aa154e))

## Changelog

All notable changes to this project will be documented in this file.
