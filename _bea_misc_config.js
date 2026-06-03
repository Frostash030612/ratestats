//此js将会被rsbuild动态加载，并且vue之前执行，请参考whp-form/src/main.ts & whp-form/rsbuild.config.ts

const MISCConfig = {
    "html": {
        breadcrumb: {
            "sdr": "/html/sg/{language}/beasg-rates-savings-include.html",
            "fdr": "/html/sg/{language}/beasg-rates-sgd-fixed-deposit-rates-include.html",
            "fcfdr": "/html/sg/{language}/beasg-rates-foreign-currency-fixed-deposit-rates-include.html",
            "contactUs": "/html/sg/{language}/beasg-contact-us-include.html"
        },
    }
};

if(typeof window == "object"){
    window.formConfig = MISCConfig
}

// export { MISCConfig }
