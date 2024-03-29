function charts_get_focusid(container, i) {
    // assure unique focusid per chart
    let focusid = 'focus-' + i + '-';
    focusid += container.replace('#', '_');
    return focusid;
}

// line chart

/**
 * line chart
 * 
 *  @param options
 *    data - [{'label':label, values: [{'x':number, 'value':value}, ... ]}, ... ]
 *    height - initial height, default 500
 *    width - initial width, default 960
 *    margin - 50 OR {top: 50, right: 50, bottom: 50, left: 50} (e.g.), default 40
 *    containerselect - e.g., '#divname', required
 *    xaxis - 'date', 'number', default 'number'
 *    xrange - array [startseq, endseq] seq are numeric, startseq may be higher then endseq
 *    xdirection - 'asc', 'desc', default 'asc'
 *    lastseq - optional sequence number to skip after, or {label:lastseq, ... } by label
 *    chartheader - optional text - if present, printed in the top center of the chart
 *    ytickincrement - y range is bumped up to next integral multiple of this value, default 1
 *    yaxislabel - optional text - if present, printed 90 deg rotated, on the left of the char
 *    statstable - {containerid: e.g., 'divname', headers: [xheader, yheader]}, optional
 */
class Chart {

    // extend config based on options
    constructor(options) {
        let that = this;
        that.options = {
            data: null,
            margin: 40,
            height: 500,
            width: 960,
            containerselect: null,
            chartheader: '',
            xaxis: 'number',
            xrange: [0, 100],
            xdirection: 'asc',
            lastseq: 0,
            yaxislabel: '',
            ytickincrement: 100,
            statstable: null,
        };
        that.options = Object.assign(that.options, options);

        // first empty containers of any elements we may have placed prior to this
        d3.selectAll(`${that.options.containerselect} .chart-element`).remove();
        if (that.options.statstable) {
            d3.selectAll(`#${that.options.statstable.containerid} .chart-element`).remove();
        }

        // default show all labels
        that.showlabels = [];

        that.xascending = that.options.xdirection == 'asc';
        if (that.options.xaxis == 'number') {
            that.xscale = d3.scaleLinear;
            // note since https://github.com/d3/d3-array/commit/22cdb3f2b1b98593a08907d17c12756404411b1d d must be scalar, not object
            // see https://github.com/d3/d3-array/issues/249
            that.bisectX = d3.bisector(function (d, x) {
                if (that.xascending) {
                    return d - x;
                } else {
                    return x - d;
                }
            }).left;

            // incr is 1 when ascending, -1 when descending
            that.lowx = that.options.xrange[0];
            that.highx = that.options.xrange[1];
            that.incr = (that.xascending) ? 1 : -1;
            that.xrange = _.range(that.lowx, that.highx + that.incr, that.incr);
            that.tickformat = function(dx) { return dx };
            that.parsex = function(x) { return x; }
            that.atlastseq = function(lastseq, thisx) {
                return (lastseq > 0 && ((that.xascending && thisx >= lastseq) || (!that.xascending && thisx <= lastseq)))
            }

            that.focustext = function(d) {return d.x + " " + d.value}
            that.formatxfortable = function(d) {return d}

        } else if (that.options.xaxis == 'date') {
            // see https://bl.ocks.org/gordlea/27370d1eea8464b04538e6d8ced39e89
            that.xscale = d3.scaleTime;
            // TODO: take xdirection option into account
            that.bisectX = d3.bisector(function(d) { return d; }).left;
            let parseDate = d3.timeParse("%m-%d");
            that.lowx = parseDate(that.options.xrange[0]);
            that.highx = parseDate(that.options.xrange[1]);
            that.xrange = [];
            for (let thisdate=new Date(that.lowx); thisdate<=that.highx; thisdate = new Date(thisdate.setDate(thisdate.getDate()+1))) {
                that.xrange.push(thisdate);
            }

            // see https://bl.ocks.org/d3noob/0e276dc70bb9184727ee47d6dd06e915
            that.tickformat = d3.timeFormat("%m/%d");

            that.parsex = function(x) {
                // translate date - maybe remove year first
                let datesplit = x.split('-');
                // check if year is present
                // TODO: needs to be special processing if previous year
                if (datesplit.length == 3) {
                    x = datesplit.slice(1).join('-');
                }
                return parseDate(x);
            }

            that.atlastseq = function(lastseq, thisx) {
                return (lastseq != '' && moment(thisx).format('MM-DD') >= lastseq)
            }

            let formatDate = d3.timeFormat("%m/%d");
            that.focustext = function(d) {return formatDate(d.x) + " " + d.value}
            that.formatxfortable = function(d) {return `${formatDate(d)}`}

        } else {
            throw 'ERROR: unknown xaxis option value: ' + that.options.xaxis;
        }

        // convert margin if necessary
        if (typeof that.options.margin == 'number') {
            that.options.margin = {
                top: that.options.margin,
                right: that.options.margin,
                bottom: that.options.margin,
                left: that.options.margin
            };
        }
    }

    // draw the chart
    draw() {
        let that = this;

        // colors copied from matplotlib v2.0 - see https://matplotlib.org/users/dflt_style_changes.html#colors-in-default-property-cycle
        let colorcycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
            '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
            '#bcbd22', '#17becf'];

        // get container
        let container = d3.select(that.options.containerselect),
            containerjs = document.querySelector(that.options.containerselect);

        // 2. Use the margin convention practice, for container
        let width = that.options.width - that.options.margin.left - that.options.margin.right, // Use the container's width
            height = that.options.height - that.options.margin.top - that.options.margin.bottom, // Use the container's height
            viewbox_width = width + that.options.margin.left + that.options.margin.right,
            viewbox_height = height + that.options.margin.top + that.options.margin.bottom;

        // 1. Add the SVG to the page and employ #2
        // for responsive solution see https://stackoverflow.com/questions/49034455/d3-chart-grows-but-wont-shrink-inside-a-flex-div#comment85075458_49034455
        // don't use width and height attributes!
        let svg = container.append("svg")
                .attr("viewBox", "0 0 " + viewbox_width + " " + viewbox_height)
                .classed("chart-element", true)
            .append("g")
                .attr("transform", "translate(" + that.options.margin.left + "," + that.options.margin.top + ")");

        // set up scales and ranges
        let x = this.xscale()
            .range([0, width]);
        let y = d3.scaleLinear()
            .range([height, 0]);

        // 5. X scale will use the x of our data
        x.domain([that.lowx, that.highx]);

        let xAxis = d3.axisBottom(x)
                .tickSize(16)
                .tickFormat(that.tickformat);

        let yAxis = d3.axisLeft(y);

        // ydomaindata is concatenation of all data for y.domain(d3.extent),
        // used to determine y domain
        let ydomaindata = [];
        for (i = 0; i < that.options.data.length; i++) {
            that.options.data[i].values.forEach(function (d) {
                d.x = that.parsex(d.x);
                // force number
                d.value = +d.value;
            });
            ydomaindata = ydomaindata.concat(that.options.data[i].values);
        }

        // seqdata is used to draw the paths so that there is a point for each number in the range
        // seqdataxvals is used for bisector function
        let seqdata = [];
        let seqdataxvals = [];
        for (let i = 0; i < that.options.data.length; i++) {
            let label = that.options.data[i].label;
            let checkvalues = _.cloneDeep(that.options.data[i].values);
            let seqvalues = [];
            seqdataxvals[i] = [];
            let currvalue = 0;
            for (let j = 0; j < that.xrange.length; j++) {
                let thisx = that.xrange[j];
                while (checkvalues.length > 0
                       && ((that.xascending && checkvalues[0].x <= thisx)
                            || (!that.xascending && checkvalues[0].x >= thisx))) {
                    let thisitem = checkvalues.shift();
                    currvalue = thisitem.value;
                }
                seqvalues.push({x: thisx, value: currvalue});
                seqdataxvals[i].push(thisx);

                // break out after current sequence
                let lastseq;
                if (typeof that.options.lastseq != 'object') {
                    lastseq = that.options.lastseq;
                } else {
                    lastseq = that.options.lastseq[label];
                }
                if (that.atlastseq(lastseq, thisx)) {
                    break;
                }
            }
            seqdata.push({label: label, values: seqvalues});
        }

        // 6. Y scale will use the dataset values
        // force up to next boundary based on ytickincrement
        y.domain([0, Math.ceil(d3.max(ydomaindata, function (d) {
            return d.value
        }) / that.options.ytickincrement) * that.options.ytickincrement]);

        // 3. Call the x axis in a group tag
        svg.append("g")
            .attr("class", "x axis")
            .attr("transform", "translate(0," + height + ")")
            // see https://bl.ocks.org/d3noob/0e276dc70bb9184727ee47d6dd06e915
            .call(xAxis) // Create an axis component with d3.axisBottom
            // https://bl.ocks.org/d3noob/3c040800ff6457717cca586ae9547dbf
            .selectAll(".tick text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-65)");

        // 4. Call the y axis in a group tag
        svg.append("g")
            .attr("class", "y axis")
            .call(yAxis); // Create an axis component with d3.axisLeft

        // y axis text
        svg.append("text")
            .attr("transform", "rotate(-90)")
            // x and y are flipped due to the rotation. see https://leanpub.com/d3-t-and-t-v4/read#leanpub-auto-the-y-axis-label
            .attr("y", 0 - that.options.margin.left)
            .attr("x", 0 - (height / 2))
            .attr("dy", "1em")
            .style("text-anchor", "middle")
            .text(that.options.yaxislabel);

        // add heading if we have one
        svg.append("g")
            .attr("class", "heading")
            .append("text")
            .attr("transform", "translate(" + width / 2 + ",-10)")
            .style("text-anchor", "middle")
            .text(that.options.chartheader);

        // 7. d3's line generator
        let line = d3.line()
            .x(function (d) {
                return x(d.x); // set the x values for the line generator
            })
            .y(function (d) {
                return y(d.value); // set the y values for the line generator
            });
        // .curve(d3.curveMonotoneX) // apply smoothing to the line

        let colormap = [];
        for (let i = 0; i < seqdata.length; i++) {
            let label = seqdata[i].label;
            colormap.push({'label': label, 'color': colorcycle[i % colorcycle.length]});

            svg.append("path")
                .style("stroke", colormap[i].color)
                .datum(seqdata[i].values)
                .attr("class", "line alllabels label-"+label)
                .attr("d", line)
                .style("fill", "none")
                .style("stroke-width", "2px");
    
            // assure unique focusid per chart
            let thisfocus = svg.append("g")
                .attr("class", "focus focuslabel-"+label)
                .attr("id", charts_get_focusid(that.options.containerselect, i))
                .style("display", "none");

            thisfocus.append("circle")
                .attr("r", 4.5)
                .style("fill", "none")
                .style("stroke", "steelblue");

            thisfocus.append("text")
                .style("text-anchor", "start")
                .attr("x", 4)
                .attr("y", 7)
                .attr("dy", ".35em");
        }

        let legend = svg.selectAll(".legend")
            .data(colormap)
            .enter().append("g")
            .attr("class", function(d) {
                return 'legend alllabels label-'+d.label;
            })
            .attr("transform", function (d, i) {
                return "translate(" + i * 90 + ",0)";
            });

        legend.append("rect")
            .attr("y", height + that.options.margin.bottom - 15)
            .attr("x", 60)
            .attr("width", 15)
            .attr("height", 15)
            .style("fill", function (d) {
                return d.color
            });

        legend.append("text")
            .attr("x", 15)
            .attr("y", height + that.options.margin.bottom - 15)
            .attr("dy", ".8em")
            .style("text-anchor", "bottom")
            .text(function (d) {
                return d.label;
            });

        // add stats table to container if requested; don't create table more than once
        // see https://stackoverflow.com/questions/9857752/correct-way-to-tell-if-my-selection-caught-any-existing-elements
        if (that.options.statstable && d3.select(`#${that.options.statstable.containerid} table`).size() == 0) {
            let statscontainer = d3.select(`#${that.options.statstable.containerid}`)
                .classed("chart-table", true);
            let statstable = statscontainer.append("table")
                .attr("class", "focus chart-element")
                .style("display", "none");
            let statstablehdr = statstable.append("thead").append("tr");
            statstablehdr
                .selectAll("th")
                .data(that.options.statstable.headers)
              .enter()
                .append("th")
                .text(d => d)
            let statstablebody = statstable.append("tbody");
            let statstablerows = statstablebody
                .selectAll("tr")
                .data(seqdata)
              .enter()
                .append("tr")
                .attr("class", d => `alllabels label-${d.label}`);
            let statstablecells = statstablerows.selectAll("td")
                .data((d) => [d.label, `${that.formatxfortable(d.x)}`, d.value])
              .enter()
                .append("td")
                // .text(d => d)
                .attr("class", (d, i) => i == 0 ? "label" : i == 1 ? "x TextCenter" : "count TextCenter");
        }

        let mouseoverlay = svg.append("rect")
            .attr("class", "overlay")
            .attr("height", height)
            .attr("width", width + that.options.margin.right)
            .style("fill", "none")
            .style("pointer-events", "all");
      
        let allfocus = that.options.statstable ? 
              d3.selectAll(`${that.options.containerselect} .focus, #${that.options.statstable.containerid} .focus`)
            : d3.selectAll(`${that.options.containerselect} .focus`);
        mouseoverlay
            .on("mouseover", function () {
                // nothing in list means show all labels
                // console.log(`entered mouseover for ${that.options.containerselect}`)
                if (that.showlabels.length == 0) {
                    allfocus.style("display", null);

                // otherwise show just the labels in the list
                } else {
                    allfocus.style("display", "none");
                    if (that.options.statstable) {
                        d3.selectAll(`#${that.options.statstable.containerid} table`).style("display", null)
                    }
                    for (let i=0; i<that.showlabels.length; i++) {
                        let label = that.showlabels[i];
                        d3.selectAll(`${that.options.containerselect} .focuslabel-${label}`).style("display", null);
                    }
                }
            })
            .on("mouseout", function () {
                allfocus.style("display", "none");
            })
            .on("mousemove", mousemove);

        function mousemove(event) {
            let x0 = x.invert(d3.pointer(event)[0]);
            // console.log(`x0=${x0}`);
            for (let i = 0; i < seqdata.length; i++) {
                // bisectX values need to be same shape as compare value x0. See https://github.com/d3/d3-array/issues/249
                let j = that.bisectX(seqdataxvals[i], x0);
                let d;
                // use d0, d1 if in range
                if (j == 0) {
                    d = seqdata[i].values[0]
                } else if (j < seqdata[i].values.length) {
                    let d0 = seqdata[i].values[j - 1],
                        d1 = seqdata[i].values[j];
                    d = x0 - d0.x > d1.x - x0 ? d1 : d0;
                } else {
                    d = seqdata[i].values[seqdata[i].values.length - 1]
                }
                let thisfocus = d3.select('#' + charts_get_focusid(that.options.containerselect, i));
                thisfocus.attr("transform", "translate(" + x(d.x) + "," + y(d.value) + ")");
                thisfocus.select("text").text(that.focustext(d));
                // console.log('d.x='+d.x+' d.value='+d.value+' x(d.x)='+x(d.x)+' y(d.value)='+y(d.value));

                // update table if requested
                if (that.options.statstable) {
                    let label = seqdata[i].label;
                    let rowselect = d3.select(`#${that.options.statstable.containerid} .label-${label}`)
                    rowselect.select(`.label`).text(label)
                    rowselect.select(`.x`).text(`${that.formatxfortable(d.x)}`)
                    rowselect.select(`.count`).text(d.value)          
                }
            }
        }
    }   // draw

    setshowlabels(labels) {
        let that = this;
        that.showlabels = labels;

        let containers = that.options.statstable ? 
              d3.selectAll(`${that.options.containerselect}, #${that.options.statstable.containerid}`)
            : d3.selectAll(`${that.options.containerselect}`);

        let alllabels = containers.selectAll(".alllabels");

        // nothing in list means show all labels
        if (that.showlabels.length == 0) {
            alllabels.style("display", null);

        // otherwise show just the labels in the list
        } else {
            alllabels.style("display", "none");
            for (let i=0; i<that.showlabels.length; i++) {
                let label = that.showlabels[i];
                d3.selectAll('.label-'+label).style("display", null);
            }
        }
    } // showlabels
}
