//此js将会被rsbuild加载，并且vue之前执行，请参考whp-form/src/main.ts & whp-form/rsbuild.config.ts

const appConfig = {
    // 对应 .env.development，i.e. process.env.NODE_ENV="development"
    "development": {
        "api": {
            // API 请求超时时间(秒)
            "time_out": 30,
            "time_out_fileUpload": 60,
            // lcoal development环境会通过proxy转发API请求到这个地址避免跨域，请参考whp-form/rsbuild.config.ts
            "base_url": "http://localhost:8090/whp/",
            // API 的根路径
            "base_path": "eform-api/v1",
        },
        // forms 中所有item将会在whp-form/src/main.ts中被乾坤框架注册为子应用
        // local development环境下子项目是单独运行在各自的 web server的，请避免端口冲突
        "forms": {
            //参考 whp-form-cln/rsbuild.config.ts
            "AEM": {
                "root": "http://localhost:9003/",
                "html": "index.html",
                "port": 9003, //本地开发运行时需要用到这个field（被对应的子项目的RsBuild.config.ts调用）, UAT/PRD 部署时用不到这个变量
            },
            "MISC": {
                "root": "http://localhost:9004/",
                "html": "index.html",
                "port": 9004, //本地开发运行时需要用到这个field（被对应的子项目的RsBuild.config.ts调用）, UAT/PRD 部署时用不到这个变量
            }
        },
        "html": {
            //header、footer远程url的base path(dev需要补齐base_path从后端走proxy，uat、prod不需补齐base_path直接从绝对路径下获取)
            "base_path": "/eform-api/v1/html",
            "header_url": "/header_footer/sg/en/header-solar-efm.shtml",
            "footer_url": "/header_footer/sg/en/footer.shtml",
            // "header_url": '/eform/uk/html/uk/{language}/include/header-solar.shtml',
            // "footer_url": '/eform/uk/html/uk/{language}/include/footer.shtml',
            // "header_url": '/header_footer/{language}/header-solar.shtml',
            // "footer_url": '/header_footer/{language}/footer.shtml',
            // "uk_header_url": '/eform/uk/html/uk/{language}/include/header-solar.shtml',
            // "uk_footer_url": '/eform/uk/html/uk/{language}/include/footer.shtml',
            // "sg_header_url": '/eform/sg/html/sg/{language}/include/header-solar.shtml',
            // "sg_footer_url": '/eform/sg/html/sg/{language}/include/footer.shtml',
        }
    },
    // 对应 .env.production, i.e. process.env.NODE_ENV="production"
    "production": {
        "api": {
            // API 请求超时时间(秒)
            "time_out": 30,
            "time_out_fileUpload": 60,
            // production 环境设置为空就行了，因为call API全都都是用相对路径的
            "base_url": "",
            // API 的根路径
            "base_path": "eform-api/v1",
        },
        // forms 中所有item将会在whp-form/src/main.ts中被乾坤框架注册为子应用
        // production环境下子项目和主项目部署在同一个web server下，乾坤框架使用相对路径获取子应用，请参考打包之后的目录层级
        "forms": {
            //参考 whp-form-cln/rsbuild.config.ts
            "AEM": {
                "root": "forms/AEM/",
                "port": 0,   //本地开发运行时需要用到这个field（被对应的子项目的RsBuild.config.ts调用）, UAT/PRD 部署时用不到这个变量
                "html": "index.html",
            },
            "MISC": {
                "root": "forms/MISC/",
                "port": 0,   //本地开发运行时需要用到这个field（被对应的子项目的RsBuild.config.ts调用）, UAT/PRD 部署时用不到这个变量
                "html": "index.html",
            }
        },
        "html": {
            "base_path": "eform-api/v1/html",
            "header_url": "/header_footer/sg/en/header-solar-efm.shtml",
            "footer_url": "/header_footer/sg/en/footer.shtml",
            // "header_url": '/eform/uk/html/uk/{language}/include/header-solar.shtml',
            // "footer_url": '/eform/uk/html/uk/{language}/include/footer.shtml',
            // "header_url": '/header_footer/{language}/header-solar.shtml',
            // "footer_url": '/header_footer/{language}/footer.shtml',
            // "uk_header_url": '/eform/uk/html/uk/{language}/include/header-solar.shtml',
            // "uk_footer_url": '/eform/uk/html/uk/{language}/include/footer.shtml',
            // "sg_header_url": '/eform/sg/html/sg/{language}/include/header-solar.shtml',
            // "sg_footer_url": '/eform/sg/html/sg/{language}/include/footer.shtml',
        }
    }
};

if(typeof window == "object"){
    window.appConfig = appConfig
}

export { appConfig }
